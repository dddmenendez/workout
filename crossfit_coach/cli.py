"""CLI interface for CrossFit Coach - quick terminal-based usage."""

import json
import os
import sys
from datetime import date

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from crossfit_coach.database import get_session
from crossfit_coach.knowledge import EQUIPMENT_CATALOG
from crossfit_coach.models import Athlete, Benchmark, Equipment, FitnessLevel, WorkoutLog
from crossfit_coach.periodization import get_current_training_context, advance_week, should_suggest_level_change

app = typer.Typer(name="cfc", help="CrossFit Coach - AI-powered training based on L1/L2 methodology")
console = Console()


def _get_client():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        console.print("Run: export ANTHROPIC_API_KEY=your-key-here")
        raise typer.Exit(1)
    return anthropic.Anthropic(api_key=api_key)


def _get_athlete(db, athlete_id: int | None = None) -> Athlete:
    if athlete_id:
        athlete = db.get(Athlete, athlete_id)
    else:
        athlete = db.query(Athlete).first()

    if not athlete:
        console.print("[red]No athlete profile found. Run: cfc setup[/red]")
        raise typer.Exit(1)
    return athlete


@app.command()
def setup():
    """Set up your athlete profile interactively."""
    console.print(Panel.fit("🏋️ CrossFit Coach - Setup", style="bold blue"))

    name = Prompt.ask("Tu nombre")

    console.print("\n[bold]Nivel de experiencia:[/bold]")
    console.print("  1. Beginner (< 6 meses)")
    console.print("  2. Intermediate (6-24 meses)")
    console.print("  3. Advanced (2-5 años)")
    console.print("  4. Elite (5+ años / competidor)")
    level_choice = IntPrompt.ask("Elige", choices=["1", "2", "3", "4"], default=1)
    level = [FitnessLevel.BEGINNER, FitnessLevel.INTERMEDIATE, FitnessLevel.ADVANCED, FitnessLevel.ELITE][level_choice - 1]

    days = IntPrompt.ask("Días de entrenamiento por semana", default=3)
    duration = IntPrompt.ask("Duración de sesión (minutos)", default=60)
    goals = Prompt.ask("Objetivos (opcional)", default="Fitness general")
    injuries = Prompt.ask("Lesiones o limitaciones (opcional)", default="Ninguna")

    # Equipment selection
    console.print("\n[bold]Equipamiento disponible:[/bold]")
    eq_list = list(EQUIPMENT_CATALOG.keys())
    for i, eq in enumerate(eq_list, 1):
        info = EQUIPMENT_CATALOG[eq]
        console.print(f"  {i:2d}. {eq:<20s} - {info['description']}")

    eq_input = Prompt.ask(
        "\nSelecciona equipamiento (números separados por coma, ej: 1,2,4,6)",
        default="",
    )

    selected_equipment = []
    if eq_input.strip():
        for idx_str in eq_input.split(","):
            idx = int(idx_str.strip()) - 1
            if 0 <= idx < len(eq_list):
                selected_equipment.append(eq_list[idx])

    if not selected_equipment:
        selected_equipment = ["none"]

    # Save to database
    db = get_session()

    # Check if athlete already exists
    existing = db.query(Athlete).first()
    if existing:
        if not Confirm.ask(f"Ya existe el perfil de '{existing.name}'. ¿Reemplazar?"):
            raise typer.Exit(0)
        db.delete(existing)
        db.commit()

    athlete = Athlete(
        name=name,
        level=level,
        training_days_per_week=days,
        session_duration_minutes=duration,
        goals=goals if goals != "Ninguna" else None,
        injuries_limitations=injuries if injuries != "Ninguna" else None,
    )
    db.add(athlete)
    db.flush()

    for eq in selected_equipment:
        db.add(Equipment(athlete_id=athlete.id, name=eq))

    db.commit()

    console.print(f"\n[green]Perfil creado para {name}![/green]")
    console.print(f"Nivel: {level.value} | Días: {days}/semana | Duración: {duration}min")
    console.print(f"Equipamiento: {', '.join(selected_equipment)}")


@app.command()
def workout(
    focus: str = typer.Option(None, "--focus", "-f", help="Focus específico (ej: 'squat strength')"),
    minutes: int = typer.Option(None, "--minutes", "-m", help="Duración disponible"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Generate today's workout."""
    from crossfit_coach.engine import generate_workout

    db = get_session()
    athlete = _get_athlete(db, athlete_id)
    client = _get_client()

    profile = {
        "name": athlete.name,
        "level": athlete.level.value,
        "training_days_per_week": athlete.training_days_per_week,
        "session_duration_minutes": minutes or athlete.session_duration_minutes,
        "goals": athlete.goals,
        "injuries_limitations": athlete.injuries_limitations,
        "equipment": [eq.name for eq in athlete.equipment],
    }

    if minutes:
        profile["available_minutes"] = minutes

    ctx = get_current_training_context(db, athlete)
    if focus:
        ctx["requested_focus"] = focus

    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    ctx["day_of_week"] = days[date.today().weekday()]

    with console.status("[bold blue]Generando tu entrenamiento...[/bold blue]"):
        result = generate_workout(client, profile, ctx)

    # Display
    console.print()
    console.print(Panel.fit(
        f"[bold]Fase: {ctx['phase']}[/bold] | Semana: {ctx['week_number']} | Intensidad: {ctx['target_intensity']}",
        title="Contexto de entrenamiento",
        style="dim",
    ))

    console.print(Panel(result.warmup, title="Warm-Up", style="yellow"))

    if result.strength_or_skill:
        console.print(Panel(result.strength_or_skill, title="Strength / Skill", style="cyan"))

    wod_title = f"WOD - {result.wod_type.upper()} ({result.target_time_domain})"
    console.print(Panel(result.wod, title=wod_title, style="bold red"))

    console.print(Panel(result.scaling_notes, title="Scaling", style="green"))
    console.print(Panel(result.cooldown, title="Cool-Down", style="blue"))
    console.print(Panel(result.coaches_notes, title="Notas del Coach", style="magenta"))

    console.print(f"\nModalidades: {', '.join(result.modalities)}")


@app.command()
def week(
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Generate a full week training plan."""
    from crossfit_coach.engine import generate_week_plan

    db = get_session()
    athlete = _get_athlete(db, athlete_id)
    client = _get_client()

    profile = {
        "name": athlete.name,
        "level": athlete.level.value,
        "training_days_per_week": athlete.training_days_per_week,
        "session_duration_minutes": athlete.session_duration_minutes,
        "goals": athlete.goals,
        "injuries_limitations": athlete.injuries_limitations,
        "equipment": [eq.name for eq in athlete.equipment],
    }

    ctx = get_current_training_context(db, athlete)

    with console.status("[bold blue]Generando plan semanal...[/bold blue]"):
        plan = generate_week_plan(client, profile, ctx)

    console.print()
    console.print(Panel.fit(
        f"[bold]{plan.focus}[/bold]\nFase: {plan.phase} | Semana: {plan.week_number}",
        title="Plan Semanal",
        style="bold blue",
    ))

    for day_plan in plan.days:
        if day_plan.rest_day:
            console.print(Panel(
                "[italic]Día de descanso - recuperación activa, movilidad, foam rolling[/italic]",
                title=f"{day_plan.day} (DESCANSO)",
                style="dim",
            ))
        elif day_plan.workout:
            w = day_plan.workout
            content = ""
            content += f"[yellow]Warm-Up:[/yellow] {w.warmup}\n\n"
            if w.strength_or_skill:
                content += f"[cyan]Strength/Skill:[/cyan] {w.strength_or_skill}\n\n"
            content += f"[red]WOD ({w.wod_type} - {w.target_time_domain}):[/red] {w.wod}\n\n"
            content += f"[green]Scaling:[/green] {w.scaling_notes}\n\n"
            content += f"[magenta]Coach:[/magenta] {w.coaches_notes}"

            console.print(Panel(content, title=f"{day_plan.day}", style="bold"))

    console.print(Panel(plan.programming_notes, title="Notas de Programación", style="magenta"))


@app.command()
def log(
    score: str = typer.Option(None, "--score", "-s", help="Score (ej: '5 rounds', '12:35')"),
    rpe: int = typer.Option(..., "--rpe", "-r", help="RPE 1-10"),
    rx: bool = typer.Option(False, "--rx", help="¿Hiciste Rx?"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notas adicionales"),
    energy: int = typer.Option(None, "--energy", "-e", help="Nivel de energía pre-WOD (1-5)"),
    sleep: int = typer.Option(None, "--sleep", help="Calidad de sueño (1-5)"),
    soreness: str = typer.Option(None, "--soreness", help="Zonas con agujetas"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Log a completed workout and get AI feedback."""
    from crossfit_coach.engine import generate_adaptation_feedback

    db = get_session()
    athlete = _get_athlete(db, athlete_id)
    client = _get_client()

    workout_log = WorkoutLog(
        athlete_id=athlete.id,
        score=score,
        rpe=rpe,
        went_rx=rx,
        notes=notes,
        energy_level=energy,
        sleep_quality=sleep,
        muscle_soreness=soreness,
    )
    db.add(workout_log)
    db.commit()

    profile = {
        "name": athlete.name,
        "level": athlete.level.value,
        "equipment": [eq.name for eq in athlete.equipment],
    }

    log_data = {
        "score": score,
        "rpe": rpe,
        "went_rx": rx,
        "notes": notes,
        "energy_level": energy,
        "sleep_quality": sleep,
        "muscle_soreness": soreness,
    }

    recent = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.athlete_id == athlete.id)
        .order_by(WorkoutLog.completed_at.desc())
        .limit(7)
        .all()
    )
    recent_dicts = [
        {"score": r.score, "rpe": r.rpe, "went_rx": r.went_rx, "notes": r.notes}
        for r in recent
    ]

    with console.status("[bold blue]Analizando tu entrenamiento...[/bold blue]"):
        feedback = generate_adaptation_feedback(client, profile, log_data, recent_dicts)

    console.print(Panel(f"Score: {score or 'N/A'} | RPE: {rpe}/10 | Rx: {'Sí' if rx else 'No'}",
                        title="Entrenamiento registrado", style="green"))
    console.print(Panel(feedback, title="Feedback de adaptación", style="magenta"))

    # Check for level suggestion
    suggestion = should_suggest_level_change(db, athlete)
    if suggestion:
        console.print(Panel(suggestion, title="Sugerencia de nivel", style="bold yellow"))


@app.command()
def benchmark(
    name: str = typer.Option(..., "--name", "-n", help="Nombre del benchmark (ej: 'Fran', 'Back Squat 1RM')"),
    value: str = typer.Option(..., "--value", "-v", help="Resultado (ej: '3:45', '120kg')"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Record a benchmark result."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    bm = Benchmark(athlete_id=athlete.id, name=name, value=value)
    db.add(bm)
    db.commit()

    console.print(f"[green]Benchmark registrado: {name} = {value}[/green]")


@app.command()
def progress(
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """View training progress and AI assessment."""
    from crossfit_coach.engine import generate_progress_assessment

    db = get_session()
    athlete = _get_athlete(db, athlete_id)
    client = _get_client()

    ctx = get_current_training_context(db, athlete)
    profile = {
        "name": athlete.name,
        "level": athlete.level.value,
        "goals": athlete.goals,
        "equipment": [eq.name for eq in athlete.equipment],
    }

    # Stats table
    table = Table(title=f"Progreso de {athlete.name}")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Total entrenamientos", str(ctx["total_workouts"]))
    table.add_row("Fase actual", ctx["phase"])
    table.add_row("Semana", str(ctx["week_number"]))
    table.add_row("RPE promedio (última semana)", str(ctx["avg_rpe"] or "N/A"))
    table.add_row("Distribución M/G/W", json.dumps(ctx["modality_distribution"]))
    console.print(table)

    # Benchmarks
    benchmarks = db.query(Benchmark).filter(Benchmark.athlete_id == athlete.id).all()
    if benchmarks:
        bm_table = Table(title="Benchmarks")
        bm_table.add_column("Nombre", style="cyan")
        bm_table.add_column("Resultado", style="green")
        bm_table.add_column("Fecha", style="dim")
        for bm in benchmarks:
            bm_table.add_row(bm.name, bm.value, str(bm.recorded_at))
        console.print(bm_table)

    # AI assessment
    with console.status("[bold blue]Generando evaluación...[/bold blue]"):
        assessment = generate_progress_assessment(client, profile, ctx)

    console.print(Panel(assessment, title="Evaluación del Coach", style="magenta"))

    suggestion = should_suggest_level_change(db, athlete)
    if suggestion:
        console.print(Panel(suggestion, title="Sugerencia de nivel", style="bold yellow"))


@app.command()
def profile(
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """View current athlete profile."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    console.print(Panel.fit(f"[bold]{athlete.name}[/bold]", title="Perfil", style="blue"))
    console.print(f"  Nivel: {athlete.level.value}")
    console.print(f"  Días/semana: {athlete.training_days_per_week}")
    console.print(f"  Duración sesión: {athlete.session_duration_minutes} min")
    console.print(f"  Objetivos: {athlete.goals or 'N/A'}")
    console.print(f"  Limitaciones: {athlete.injuries_limitations or 'N/A'}")
    console.print(f"  Equipamiento: {', '.join(eq.name for eq in athlete.equipment)}")


if __name__ == "__main__":
    app()
