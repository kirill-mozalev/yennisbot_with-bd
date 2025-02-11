import logging
from database import create_connection
from itertools import combinations
from datetime import datetime, timedelta
# Настройка логирования

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_logs.txt"),  # Логи будут записываться в файл bot_logs.txt
    ]
)
logger = logging.getLogger(__name__)

def generate_matches(session_id, round_number):
    """Генерирует матчи для текущего круга."""
    conn = create_connection()
    cursor = conn.cursor()

    # Очищаем матчи текущего круга перед генерацией нового
    cursor.execute('DELETE FROM matches WHERE session_id = ? AND round_number = ?', (session_id, round_number))
    conn.commit()

    # Получаем список игроков
    cursor.execute('SELECT player_id FROM players WHERE session_id = ?', (session_id,))
    players = [row[0] for row in cursor.fetchall()]

    # Создаем все возможные пары матчей
    matches = list(combinations(players, 2))

    # Распределяем матчи с учетом перерывов
    scheduled_matches = []
    player_last_match = {player: -1 for player in players}  # Время последнего матча для каждого игрока

    current_time = 0
    while matches:
        for match in matches[:]:
            player1, player2 = match
            # Проверяем, что оба игрока отдыхали после последнего матча
            if player_last_match[player1] < current_time and player_last_match[player2] < current_time:
                scheduled_matches.append((player1, player2, current_time))
                player_last_match[player1] = current_time
                player_last_match[player2] = current_time
                matches.remove(match)
        current_time += 1

    # Сохраняем матчи в базу данных
    for match in scheduled_matches:
        player1, player2, _ = match
        cursor.execute('''
                INSERT INTO matches (session_id, round_number, player1_id, player2_id, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (session_id, round_number, player1, player2))

    conn.commit()
    conn.close()
    logger.info(f"Матчи сгенерированы для сессии {session_id}, круг {round_number}.")

def get_session_stats(session_id):
    """Возвращает общую статистику за все круги."""
    conn = create_connection()
    cursor = conn.cursor()

    # Получаем статистику побед для каждого игрока за все круги
    cursor.execute('''
    SELECT p.name, COUNT(m.winner_id) as wins
    FROM players p
    LEFT JOIN matches m ON p.player_id = m.winner_id
    WHERE p.session_id = ?
    GROUP BY p.player_id
    ORDER BY wins DESC
    ''', (session_id,))
    stats = cursor.fetchall()

    conn.close()
    logger.info(f"Статистика за сессию {session_id} получена.")
    return stats

def get_current_round_stats(session_id, round_number):
    """Возвращает статистику за текущий круг."""
    conn = create_connection()
    cursor = conn.cursor()

    # Получаем статистику побед для каждого игрока за текущий круг
    cursor.execute('''
    SELECT p.name, COUNT(m.winner_id) as wins
    FROM players p
    LEFT JOIN matches m ON p.player_id = m.winner_id
    WHERE p.session_id = ? AND m.round_number = ?
    GROUP BY p.player_id
    ORDER BY wins DESC
    ''', (session_id, round_number))
    stats = cursor.fetchall()

    conn.close()
    logger.info(f"Статистика за круг {round_number} в сессии {session_id} получена.")
    return stats

def get_monthly_stats(chat_id=None):
    """Возвращает статистику игроков и их побед за текущий месяц."""
    conn = create_connection()
    cursor = conn.cursor()

    # Получаем начало и конец текущего месяца
    today = datetime.today()
    first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    # Базовый запрос для получения статистики
    query = '''
    SELECT p.name, COUNT(m.winner_id) as wins
    FROM players p
    LEFT JOIN matches m ON p.player_id = m.winner_id
    WHERE m.winner_id IS NOT NULL
    AND m.created_at BETWEEN ? AND ?
    '''

    # Если передан chat_id, фильтруем по нему
    if chat_id:
        query += ' AND p.session_id IN (SELECT session_id FROM sessions WHERE chat_id = ?)'
        params = (first_day_of_month.strftime('%Y-%m-%d %H:%M:%S'), last_day_of_month.strftime('%Y-%m-%d %H:%M:%S'), chat_id)
    else:
        params = (first_day_of_month.strftime('%Y-%m-%d %H:%M:%S'), last_day_of_month.strftime('%Y-%m-%d %H:%M:%S'))

    query += ' GROUP BY p.name ORDER BY wins DESC'

    cursor.execute(query, params)
    stats = cursor.fetchall()

    conn.close()
    logger.info(f"Статистика за текущий месяц получена: {stats}")
    return stats