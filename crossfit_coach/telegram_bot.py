"""Telegram bot for CrossFit Coach - users interact via chat commands."""

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from crossfit_coach.auth import hash_password, verify_password, create_token
from crossfit_coach.database import Base, get_engine, get_session
from crossfit_coach.engine import (
    generate_adaptation_feedback,
    generate_progress_assessment,
    generate_week_plan,
    generate_workout,
)
from crossfit_coach.models import (
    Athlete,
    Benchmark,
    Equipment,
    FitnessLevel,
    User,
    WorkoutLog,
)
from crossfit_coach.periodization import (
    advance_week,
    get_current_training_context,
    should_suggest_level_change,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states for setup
SETUP_NAME, SETUP_LEVEL, SETUP_DAYS, SETUP_DURATION, SETUP_EQUIPMENT = range(5)
REG_PASSWORD = range(1)
LOGIN_PASSWORD = range(1)


def get_user_by_chat(chat_id: int) -> User | None:
    db = get_session()
    try:
        return db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()


def get_athlete_for_user(user: User) -> Athlete | None:
    db = get_session()
    try:
        return db.query(Athlete).filter(Athlete.user_id == user.id).first()
    finally:
        db.close()


# --- /start ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if user:
        await update.message.reply_text(
            f"¡Hola de nuevo, {user.username}! 💪\n\n"
            "Comandos disponibles:\n"
            "/workout - Generar workout de hoy\n"
            "/week - Plan semanal completo\n"
            "/log <score> <rpe> - Registrar resultado\n"
            "/progress - Ver tu progreso\n"
            "/benchmark <nombre> <valor> - Registrar PR\n"
            "/advance - Avanzar semana de entrenamiento"
        )
    else:
        await update.message.reply_text(
            "¡Bienvenido al CrossFit Coach! 🏋️\n\n"
            "Para empezar necesitás registrarte:\n"
            "/register <usuario> - Crear cuenta nueva\n"
            "/login <usuario> - Iniciar sesión con cuenta existente"
        )


# --- /register ---

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Uso: /register <nombre_de_usuario>")
        return ConversationHandler.END

    username = args[0]
    db = get_session()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            await update.message.reply_text("Ese nombre de usuario ya existe. Probá con otro.")
            return ConversationHandler.END
    finally:
        db.close()

    context.user_data["reg_username"] = username
    await update.message.reply_text(f"Elegí una contraseña para '{username}' (mín. 6 caracteres):")
    return 0  # REG_PASSWORD


async def register_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    if len(password) < 6:
        await update.message.reply_text("La contraseña debe tener al menos 6 caracteres. Intentá de nuevo:")
        return 0

    username = context.user_data["reg_username"]
    db = get_session()
    try:
        user = User(
            username=username,
            password_hash=hash_password(password),
            telegram_chat_id=update.effective_chat.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        await update.message.reply_text(
            f"✅ Cuenta creada: {username}\n\n"
            "Ahora configurá tu perfil de atleta con /setup"
        )
    finally:
        db.close()

    return ConversationHandler.END


# --- /login ---

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Uso: /login <nombre_de_usuario>")
        return ConversationHandler.END

    username = args[0]
    db = get_session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            await update.message.reply_text("Usuario no encontrado.")
            return ConversationHandler.END
    finally:
        db.close()

    context.user_data["login_username"] = username
    await update.message.reply_text("Ingresá tu contraseña:")
    return 0  # LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    username = context.user_data["login_username"]

    db = get_session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            await update.message.reply_text("Contraseña incorrecta.")
            return ConversationHandler.END

        user.telegram_chat_id = update.effective_chat.id
        db.commit()
        await update.message.reply_text(
            f"✅ Sesión iniciada como {username}\n"
            "Usá /workout para generar tu entrenamiento."
        )
    finally:
        db.close()

    return ConversationHandler.END


# --- /setup (athlete profile) ---

async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Primero registrate con /register <usuario>")
        return ConversationHandler.END

    context.user_data["setup_user_id"] = user.id
    await update.message.reply_text("¿Cuál es tu nombre?")
    return SETUP_NAME


async def setup_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "¿Cuál es tu nivel?\n"
        "1 - Beginner (< 6 meses)\n"
        "2 - Intermediate (6-24 meses)\n"
        "3 - Advanced (2-5 años)\n"
        "4 - Elite (5+ años)"
    )
    return SETUP_LEVEL


async def setup_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    levels = {"1": FitnessLevel.BEGINNER, "2": FitnessLevel.INTERMEDIATE,
              "3": FitnessLevel.ADVANCED, "4": FitnessLevel.ELITE}
    choice = update.message.text.strip()
    context.user_data["level"] = levels.get(choice, FitnessLevel.BEGINNER)
    await update.message.reply_text("¿Cuántos días por semana querés entrenar? (1-7)")
    return SETUP_DAYS


async def setup_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        days = max(1, min(7, days))
    except ValueError:
        days = 3
    context.user_data["days"] = days
    await update.message.reply_text("¿Duración de sesión en minutos? (20-120)")
    return SETUP_DURATION


async def setup_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mins = int(update.message.text.strip())
        mins = max(20, min(120, mins))
    except ValueError:
        mins = 60
    context.user_data["duration"] = mins
    await update.message.reply_text(
        "¿Qué equipamiento tenés? (separado por comas)\n"
        "Ejemplos: barbell, pull_up_bar, kettlebell, rings, rower, assault_bike, dumbbells, box, wall_ball, rope\n\n"
        "Escribí 'ninguno' si no tenés nada."
    )
    return SETUP_EQUIPMENT


async def setup_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "ninguno":
        equipment = []
    else:
        equipment = [e.strip() for e in text.split(",") if e.strip()]

    db = get_session()
    try:
        user_id = context.user_data["setup_user_id"]
        existing = db.query(Athlete).filter(Athlete.user_id == user_id).first()
        if existing:
            await update.message.reply_text("Ya tenés un perfil. Usá /workout para entrenar.")
            return ConversationHandler.END

        athlete = Athlete(
            user_id=user_id,
            name=context.user_data["name"],
            level=context.user_data["level"],
            training_days_per_week=context.user_data["days"],
            session_duration_minutes=context.user_data["duration"],
        )
        db.add(athlete)
        db.flush()

        for eq in equipment:
            db.add(Equipment(athlete_id=athlete.id, name=eq))

        db.commit()
        await update.message.reply_text(
            f"✅ Perfil creado: {athlete.name} ({athlete.level.value})\n"
            f"📅 {athlete.training_days_per_week} días/semana, {athlete.session_duration_minutes} min/sesión\n"
            f"🏋️ Equipamiento: {', '.join(equipment) or 'ninguno'}\n\n"
            "¡Listo! Usá /workout para tu primer entrenamiento."
        )
    finally:
        db.close()

    return ConversationHandler.END


# --- /workout ---

async def workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

        profile = {
            "name": athlete.name,
            "level": athlete.level.value,
            "training_days_per_week": athlete.training_days_per_week,
            "session_duration_minutes": athlete.session_duration_minutes,
            "goals": athlete.goals,
            "injuries_limitations": athlete.injuries_limitations,
            "equipment": [eq.name for eq in athlete.equipment],
        }

        training_ctx = get_current_training_context(db, athlete)
        from datetime import date
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        training_ctx["day_of_week"] = days[date.today().weekday()]

        w = generate_workout(profile, training_ctx)

        msg = f"🏋️ *WORKOUT DEL DÍA*\n\n"
        msg += f"📝 *Warm-up:*\n{w.warmup}\n\n"
        if w.strength_or_skill:
            msg += f"💪 *Fuerza/Skill:*\n{w.strength_or_skill}\n\n"
        msg += f"🔥 *WOD ({w.wod_type.value.upper()})* - {w.target_time_domain}\n{w.wod}\n\n"
        msg += f"📊 *Modalidades:* {', '.join(w.modalities)}\n"
        msg += f"⚖️ *Scaling:*\n{w.scaling_notes}\n\n"
        msg += f"🧊 *Cooldown:*\n{w.cooldown}\n\n"
        msg += f"🗒️ *Notas del coach:*\n{w.coaches_notes}"

        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()


# --- /week ---

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

        profile = {
            "name": athlete.name,
            "level": athlete.level.value,
            "training_days_per_week": athlete.training_days_per_week,
            "session_duration_minutes": athlete.session_duration_minutes,
            "goals": athlete.goals,
            "injuries_limitations": athlete.injuries_limitations,
            "equipment": [eq.name for eq in athlete.equipment],
        }

        training_ctx = get_current_training_context(db, athlete)
        plan = generate_week_plan(profile, training_ctx)

        msg = f"📅 *PLAN SEMANAL* - Semana {plan.week_number}\n"
        msg += f"📊 Fase: {plan.phase.value} | Foco: {plan.focus}\n\n"

        for day in plan.days:
            if day.rest_day:
                msg += f"*{day.day}:* 🛌 Descanso\n\n"
            elif day.workout:
                w = day.workout
                msg += f"*{day.day}:* {w.wod_type.value.upper()}\n"
                msg += f"{w.wod}\n\n"

        msg += f"📝 {plan.programming_notes}"

        # Telegram has 4096 char limit
        if len(msg) > 4000:
            for i in range(0, len(msg), 4000):
                await update.message.reply_text(msg[i:i+4000], parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()


# --- /log ---

async def log_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /log <score> <rpe>\n"
            "Ejemplo: /log 5rounds+3reps 7\n"
            "RPE: 1 (fácil) a 10 (máximo esfuerzo)"
        )
        return

    score = args[0]
    try:
        rpe = int(args[1])
        rpe = max(1, min(10, rpe))
    except ValueError:
        await update.message.reply_text("RPE debe ser un número del 1 al 10")
        return

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

        log = WorkoutLog(
            athlete_id=athlete.id,
            score=score,
            rpe=rpe,
            went_rx=True,
        )
        db.add(log)
        db.commit()

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

        feedback = generate_adaptation_feedback(
            {"score": score, "rpe": rpe, "went_rx": True},
            recent_dicts,
        )

        await update.message.reply_text(
            f"✅ Resultado registrado\n"
            f"Score: {score} | RPE: {rpe}\n\n"
            f"📊 {feedback}"
        )
    finally:
        db.close()


# --- /progress ---

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

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
        assessment = generate_progress_assessment(profile, ctx)
        level_suggestion = should_suggest_level_change(db, athlete)

        msg = f"📊 *TU PROGRESO*\n\n"
        msg += f"💪 Workouts totales: {ctx['total_workouts']}\n"
        msg += f"📅 Semana: {ctx['week_number']} | Fase: {ctx['phase'].value}\n"
        if ctx['avg_rpe']:
            msg += f"🎯 RPE promedio última semana: {ctx['avg_rpe']:.1f}\n"
        msg += f"\n{assessment}"
        if level_suggestion:
            msg += f"\n\n🔄 {level_suggestion}"

        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()


# --- /benchmark ---

async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /benchmark <nombre> <valor>\n"
            "Ejemplo: /benchmark Fran 3:45\n"
            "Ejemplo: /benchmark BackSquat1RM 120kg"
        )
        return

    name = args[0]
    value = " ".join(args[1:])

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

        bm = Benchmark(athlete_id=athlete.id, name=name, value=value)
        db.add(bm)
        db.commit()

        await update.message.reply_text(f"✅ Benchmark registrado: {name} = {value}")
    finally:
        db.close()


# --- /advance ---

async def advance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Registrate primero con /register <usuario>")
        return

    db = get_session()
    try:
        athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
        if not athlete:
            await update.message.reply_text("Configurá tu perfil primero con /setup")
            return

        week_obj = advance_week(db, athlete)
        await update.message.reply_text(
            f"⏭️ Semana avanzada\n"
            f"Semana {week_obj.week_number} | Fase: {week_obj.phase.value}\n"
            f"Foco: {week_obj.focus}\n"
            f"Intensidad: {week_obj.target_intensity}"
        )
    finally:
        db.close()


# --- Cancel handler ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable")
        return

    # Initialize database
    engine = get_engine()
    Base.metadata.create_all(engine)

    app = Application.builder().token(token).build()

    # Conversation handlers for multi-step flows
    register_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={0: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_password)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={0: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    setup_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            SETUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_name)],
            SETUP_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_level)],
            SETUP_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_days)],
            SETUP_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_duration)],
            SETUP_EQUIPMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_equipment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(register_handler)
    app.add_handler(login_handler)
    app.add_handler(setup_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("workout", workout))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("log", log_result))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("benchmark", benchmark))
    app.add_handler(CommandHandler("advance", advance))

    logger.info("Bot started! Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
