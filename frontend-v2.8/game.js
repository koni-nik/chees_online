// game.js - Шахматы v2.8 с системой аутентификации
// Базовая версия, которая загружает функциональность из v2.7

// Проверяем наличие authManager
if (typeof authManager === 'undefined') {
    console.error('authManager не найден. Убедитесь, что auth.js загружен перед game.js');
}

// Временно используем функциональность из v2.7 через динамическую загрузку
// В будущем можно будет создать полную версию с интеграцией auth

// Минимальная инициализация игры
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем авторизацию перед инициализацией игры
    if (typeof authManager !== 'undefined' && !authManager.isAuthenticated()) {
        console.log('Пользователь не авторизован. Игра будет доступна после входа.');
        return;
    }
    
    // Инициализация будет выполнена после загрузки основного кода
    // Пока используем fallback на v2.7 через backend
    console.log('Инициализация игры v2.8...');
    
    // Базовые обработчики кнопок меню
    const btnOnline = document.getElementById('btn-online');
    const btnLocal = document.getElementById('btn-local');
    const btnMatchmaking = document.getElementById('btn-matchmaking');
    const btnStats = document.getElementById('btn-stats');
    const btnTournaments = document.getElementById('btn-tournaments');
    const btnLogout = document.getElementById('btn-logout');
    const btnBackRoom = document.getElementById('btn-back-room');
    const btnJoin = document.getElementById('btn-join');
    const btnCreate = document.getElementById('btn-create');
    
    if (btnOnline) {
        btnOnline.addEventListener('click', () => {
            document.getElementById('main-menu').classList.add('hidden');
            document.getElementById('room-screen').classList.remove('hidden');
        });
    }
    
    if (btnBackRoom) {
        btnBackRoom.addEventListener('click', () => {
            document.getElementById('room-screen').classList.add('hidden');
            document.getElementById('main-menu').classList.remove('hidden');
        });
    }
    
    if (btnJoin) {
        btnJoin.addEventListener('click', () => {
            const roomId = document.getElementById('room-input').value || generateRoomId();
            joinRoom(roomId);
        });
    }
    
    if (btnCreate) {
        btnCreate.addEventListener('click', () => {
            const roomId = generateRoomId();
            joinRoom(roomId);
        });
    }
    
    if (btnLogout && typeof authManager !== 'undefined') {
        btnLogout.addEventListener('click', async () => {
            await authManager.logout();
            document.getElementById('main-menu').classList.add('hidden');
            document.getElementById('auth-screen').classList.remove('hidden');
        });
    }
    
    // Обработчики для других кнопок
    if (btnLocal) {
        btnLocal.addEventListener('click', () => {
            alert('Локальная игра будет доступна в полной версии');
        });
    }
    
    if (btnMatchmaking) {
        btnMatchmaking.addEventListener('click', () => {
            alert('Matchmaking будет доступен в полной версии');
        });
    }
    
    if (btnStats) {
        btnStats.addEventListener('click', () => {
            alert('Статистика будет доступна в полной версии');
        });
    }
    
    if (btnTournaments) {
        btnTournaments.addEventListener('click', () => {
            document.getElementById('main-menu').classList.add('hidden');
            document.getElementById('tournament-screen').classList.remove('hidden');
        });
    }
});

// Генерация ID комнаты
function generateRoomId() {
    return Math.random().toString(36).substring(2, 10);
}

// Подключение к комнате
function joinRoom(roomId) {
    // Получаем player_id из authManager
    let playerId = 'guest_' + Math.random().toString(36).substring(2, 9);
    
    if (typeof authManager !== 'undefined' && authManager.currentUser) {
        playerId = authManager.currentUser.player_id || authManager.currentUser.email?.split('@')[0] || playerId;
    }
    
    // Переходим к игре
    document.getElementById('room-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    
    // Устанавливаем информацию о комнате
    const currentRoomEl = document.getElementById('current-room');
    if (currentRoomEl) {
        currentRoomEl.textContent = roomId;
    }
    
    // Инициализируем WebSocket соединение
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${roomId}/${playerId}`;
    
    console.log('Подключение к WebSocket:', wsUrl);
    
    // Здесь будет инициализация WebSocket и игровой логики
    // Пока используем fallback на v2.7 через backend
    alert(`Подключение к комнате ${roomId}. Полная функциональность будет доступна после загрузки game.js из v2.7`);
}

// Экспорт для использования в других скриптах
window.chessGameV28 = {
    joinRoom: joinRoom,
    generateRoomId: generateRoomId
};

