"""CLI interface for CrossFit Coach - quick terminal-based usage."""

import json
from datetime import date

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from crossfit_coach.config import get_active_athlete_id, set_active_athlete_id
from crossfit_coach.database import get_session
from crossfit_coach.engine import (
    generate_adaptation_feedback,
    generate_progress_assessment,
    generate_week_plan,
    generate_workout,
)
from crossfit_coach.knowledge import EQUIPMENT_CATALOG
from crossfit_coach.models import Athlete, Benchmark, Equipment, FitnessLevel, PlannedWorkout, TrainingWeek, WorkoutLog, WorkoutType
from crossfit_coach.periodization import advance_week, get_current_training_context, should_suggest_level_change

app = typer.Typer(name="cfc", help="CrossFit Coach - Entrenamiento basado en metodología L1/L2")
console = Console()


def _get_athlete(db, athlete_id: int | None = None) -> Athlete:
    if athlete_id:
        athlete = db.get(Athlete, athlete_id)
    else:
        active_id = get_active_athlete_id()
        if active_id:
            athlete = db.get(Athlete, active_id)
        else:
            athlete = db.query(Athlete).first()

    if not athlete:
        console.print("[red]No hay perfil de atleta. Ejecuta: cfc setup[/red]")
        raise typer.Exit(1)
    return athlete


def _athlete_to_profile(athlete: Athlete) -> dict:
    return {
        "name": athlete.name,
        "level": athlete.level.value,
        "training_days_per_week": athlete.training_days_per_week,
        "session_duration_minutes": athlete.session_duration_minutes,
        "goals": athlete.goals,
        "injuries_limitations": athlete.injuries_limitations,
        "equipment": [eq.name for eq in athlete.equipment],
    }


@app.command()
def setup():
    """Configura tu perfil de atleta."""
    console.print(Panel.fit("CrossFit Coach - Setup", style="bold blue"))

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
    db.refresh(athlete)

    set_active_athlete_id(athlete.id)

    console.print(f"\n[green]Perfil creado para {name} (ID: {athlete.id})![/green]")
    console.print(f"Nivel: {level.value} | Días: {days}/semana | Duración: {duration}min")
    console.print(f"Equipamiento: {', '.join(selected_equipment)}")
    console.print(f"[dim]Atleta activo establecido a: {name}[/dim]")


@app.command()
def workout(
    focus: str = typer.Option(None, "--focus", "-f", help="Focus específico (ej: 'squat strength')"),
    minutes: int = typer.Option(None, "--minutes", "-m", help="Duración disponible"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Genera el entrenamiento de hoy."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    profile = _athlete_to_profile(athlete)
    if minutes:
        profile["available_minutes"] = minutes

    ctx = get_current_training_context(db, athlete)
    if focus:
        ctx["requested_focus"] = focus

    days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    ctx["day_of_week"] = days_es[date.today().weekday()]

    result = generate_workout(profile, ctx)

    # Save to DB
    pw = PlannedWorkout(
        athlete_id=athlete.id,
        day_of_week=date.today().isoweekday(),
        workout_type=result.wod_type,
        description=result.wod,
        warmup=result.warmup,
        strength=result.strength_or_skill,
        wod=result.wod,
        cooldown=result.cooldown,
        modalities=",".join(result.modalities),
        scaling_notes=result.scaling_notes,
        coaches_notes=result.coaches_notes,
        target_time_domain=result.target_time_domain,
    )
    db.add(pw)
    db.commit()
    db.refresh(pw)

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
    console.print(f"[dim]Guardado como workout #{pw.id}. Usa 'cfc log --workout-id {pw.id}' para registrar resultado.[/dim]")


@app.command()
def week(
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Genera un plan semanal completo."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    profile = _athlete_to_profile(athlete)
    ctx = get_current_training_context(db, athlete)

    plan = generate_week_plan(profile, ctx)

    # Save to DB
    tw = TrainingWeek(
        athlete_id=athlete.id,
        week_number=plan.week_number,
        phase=plan.phase,
        focus=plan.focus,
        target_intensity=ctx.get("target_intensity", "moderate"),
    )
    db.add(tw)
    db.flush()

    day_map = {"Lunes": 1, "Martes": 2, "Miércoles": 3, "Jueves": 4, "Viernes": 5, "Sábado": 6, "Domingo": 7}
    saved_ids = []
    for day_plan in plan.days:
        if not day_plan.rest_day and day_plan.workout:
            w = day_plan.workout
            pw = PlannedWorkout(
                athlete_id=athlete.id,
                week_id=tw.id,
                day_of_week=day_map.get(day_plan.day, 1),
                workout_type=w.wod_type,
                description=w.wod,
                warmup=w.warmup,
                strength=w.strength_or_skill,
                wod=w.wod,
                cooldown=w.cooldown,
                modalities=",".join(w.modalities),
                scaling_notes=w.scaling_notes,
                coaches_notes=w.coaches_notes,
                target_time_domain=w.target_time_domain,
            )
            db.add(pw)
            db.flush()
            saved_ids.append(pw.id)
    db.commit()

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
    console.print(f"\n[dim]Semana guardada. IDs de workouts: {saved_ids}[/dim]")


@app.command()
def log(
    score: str = typer.Option(None, "--score", "-s", help="Score (ej: '5 rounds', '12:35')"),
    rpe: int = typer.Option(..., "--rpe", "-r", help="RPE 1-10"),
    rx: bool = typer.Option(False, "--rx", help="¿Hiciste Rx?"),
    notes: str = typer.Option(None, "--notes", "-n", help="Notas adicionales"),
    energy: int = typer.Option(None, "--energy", "-e", help="Nivel de energía pre-WOD (1-5)"),
    sleep: int = typer.Option(None, "--sleep", help="Calidad de sueño (1-5)"),
    soreness: str = typer.Option(None, "--soreness", help="Zonas con agujetas"),
    workout_id: int = typer.Option(None, "--workout-id", "-w", help="ID del workout planificado"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Registra un entrenamiento completado y recibe feedback."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    if workout_id:
        pw = db.get(PlannedWorkout, workout_id)
        if not pw:
            console.print(f"[red]Workout #{workout_id} no encontrado.[/red]")
            raise typer.Exit(1)
        if pw.log:
            console.print(f"[yellow]Workout #{workout_id} ya tiene un log registrado.[/yellow]")
            raise typer.Exit(1)

    workout_log = WorkoutLog(
        athlete_id=athlete.id,
        planned_workout_id=workout_id,
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

    feedback = generate_adaptation_feedback(log_data, recent_dicts)

    console.print(Panel(f"Score: {score or 'N/A'} | RPE: {rpe}/10 | Rx: {'Sí' if rx else 'No'}",
                        title="Entrenamiento registrado", style="green"))
    console.print(Panel(feedback, title="Feedback de adaptación", style="magenta"))

    suggestion = should_suggest_level_change(db, athlete)
    if suggestion:
        console.print(Panel(suggestion, title="Sugerencia de nivel", style="bold yellow"))


@app.command()
def benchmark(
    name: str = typer.Option(..., "--name", "-n", help="Nombre del benchmark (ej: 'Fran', 'Back Squat 1RM')"),
    value: str = typer.Option(..., "--value", "-v", help="Resultado (ej: '3:45', '120kg')"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Registra un resultado de benchmark."""
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
    """Ver progreso y evaluación."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    ctx = get_current_training_context(db, athlete)
    profile = _athlete_to_profile(athlete)

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

    assessment = generate_progress_assessment(profile, ctx)

    console.print(Panel(assessment, title="Evaluación", style="magenta"))

    suggestion = should_suggest_level_change(db, athlete)
    if suggestion:
        console.print(Panel(suggestion, title="Sugerencia de nivel", style="bold yellow"))


@app.command()
def profile(
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Ver perfil actual."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    console.print(Panel.fit(f"[bold]{athlete.name}[/bold]", title="Perfil", style="blue"))
    console.print(f"  Nivel: {athlete.level.value}")
    console.print(f"  Días/semana: {athlete.training_days_per_week}")
    console.print(f"  Duración sesión: {athlete.session_duration_minutes} min")
    console.print(f"  Objetivos: {athlete.goals or 'N/A'}")
    console.print(f"  Limitaciones: {athlete.injuries_limitations or 'N/A'}")
    console.print(f"  Equipamiento: {', '.join(eq.name for eq in athlete.equipment)}")


@app.command()
def athletes():
    """Listar todos los atletas registrados."""
    db = get_session()
    all_athletes = db.query(Athlete).order_by(Athlete.id).all()

    if not all_athletes:
        console.print("[yellow]No hay atletas registrados. Ejecuta: cfc setup[/yellow]")
        raise typer.Exit(0)

    active_id = get_active_athlete_id()

    table = Table(title="Atletas registrados")
    table.add_column("ID", style="dim")
    table.add_column("Nombre", style="bold")
    table.add_column("Nivel", style="cyan")
    table.add_column("Días/sem", style="green")
    table.add_column("Duración", style="green")
    table.add_column("Activo", style="magenta")

    for a in all_athletes:
        is_active = "* " if a.id == active_id else ""
        table.add_row(
            str(a.id),
            f"{is_active}{a.name}",
            a.level.value,
            str(a.training_days_per_week),
            f"{a.session_duration_minutes}min",
            "Sí" if a.id == active_id else "",
        )

    console.print(table)
    console.print(f"\n[dim]Usa 'cfc switch <id>' para cambiar de atleta activo.[/dim]")


@app.command()
def switch(
    athlete_id: int = typer.Argument(..., help="ID del atleta a activar"),
):
    """Cambiar el atleta activo."""
    db = get_session()
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        console.print(f"[red]Atleta #{athlete_id} no encontrado.[/red]")
        console.print("[dim]Usa 'cfc athletes' para ver los IDs disponibles.[/dim]")
        raise typer.Exit(1)

    set_active_athlete_id(athlete.id)
    console.print(f"[green]Atleta activo: {athlete.name} (ID: {athlete.id})[/green]")


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Número de entrenamientos a mostrar"),
    athlete_id: int = typer.Option(None, "--athlete", "-a", help="ID del atleta"),
):
    """Ver historial de entrenamientos guardados."""
    db = get_session()
    athlete = _get_athlete(db, athlete_id)

    workouts = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.athlete_id == athlete.id)
        .order_by(PlannedWorkout.created_at.desc())
        .limit(limit)
        .all()
    )

    if not workouts:
        console.print("[yellow]No hay entrenamientos guardados. Genera uno con: cfc workout[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"Historial de {athlete.name} (últimos {limit})")
    table.add_column("ID", style="dim")
    table.add_column("Fecha", style="cyan")
    table.add_column("Día", style="cyan")
    table.add_column("Tipo", style="green")
    table.add_column("Dominio", style="yellow")
    table.add_column("Modalidades")
    table.add_column("Log", style="magenta")

    days_es = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb", 7: "Dom"}
    for w in workouts:
        table.add_row(
            str(w.id),
            w.created_at.strftime("%Y-%m-%d %H:%M"),
            days_es.get(w.day_of_week, "?"),
            w.workout_type.value,
            w.target_time_domain or "-",
            w.modalities.replace(",", ", "),
            "Sí" if w.log else "No",
        )

    console.print(table)
    console.print(f"\n[dim]Total guardados: {db.query(PlannedWorkout).filter(PlannedWorkout.athlete_id == athlete.id).count()}[/dim]")


@app.command()
def show(
    workout_id: int = typer.Argument(..., help="ID del workout a mostrar"),
):
    """Ver detalle de un entrenamiento guardado."""
    db = get_session()
    w = db.get(PlannedWorkout, workout_id)
    if not w:
        console.print(f"[red]Workout #{workout_id} no encontrado.[/red]")
        raise typer.Exit(1)

    days_es = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}

    console.print(Panel.fit(
        f"[bold]Workout #{w.id}[/bold] | {days_es.get(w.day_of_week, '?')} | {w.created_at.strftime('%Y-%m-%d')}",
        style="blue",
    ))

    if w.warmup:
        console.print(Panel(w.warmup, title="Warm-Up", style="yellow"))
    if w.strength:
        console.print(Panel(w.strength, title="Strength / Skill", style="cyan"))
    if w.wod:
        console.print(Panel(w.wod, title=f"WOD - {w.workout_type.value.upper()} ({w.target_time_domain or '?'})", style="bold red"))
    if w.scaling_notes:
        console.print(Panel(w.scaling_notes, title="Scaling", style="green"))
    if w.cooldown:
        console.print(Panel(w.cooldown, title="Cool-Down", style="blue"))
    if w.coaches_notes:
        console.print(Panel(w.coaches_notes, title="Notas del Coach", style="magenta"))

    console.print(f"\nModalidades: {w.modalities.replace(',', ', ')}")

    if w.log:
        console.print(Panel(
            f"Score: {w.log.score or 'N/A'} | RPE: {w.log.rpe}/10 | Rx: {'Sí' if w.log.went_rx else 'No'}",
            title="Resultado registrado",
            style="green",
        ))
    else:
        console.print(f"\n[dim]Sin resultado. Usa: cfc log --workout-id {w.id} -r <rpe>[/dim]")


if __name__ == "__main__":
    app()
