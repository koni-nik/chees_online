// game.js - Шахматы v2.8 с системой аутентификации
// Загружаем функциональность из v2.7 и обновляем для использования auth

// Проверяем наличие authManager
if (typeof authManager === 'undefined') {
    console.error('authManager не найден. Убедитесь, что auth.js загружен перед game.js');
}

// Загружаем game.js из v2.7 через динамический импорт
// Это позволит использовать всю функциональность v2.7 с обновлениями для v2.8
(async function() {
    try {
        // Загружаем скрипт из v2.7
        const script = document.createElement('script');
        script.src = '/v2.7/game.js';
        script.onload = () => {
            console.log('Game.js v2.7 загружен, обновляем для v2.8...');
            initV28Updates();
        };
        script.onerror = () => {
            console.error('Не удалось загрузить game.js v2.7, используем базовую версию');
            initBasicGame();
        };
        document.head.appendChild(script);
    } catch (e) {
        console.error('Ошибка загрузки game.js v2.7:', e);
        initBasicGame();
    }
})();

function initV28Updates() {
    // Обновляем playerId для использования из authManager
    if (window.game && typeof authManager !== 'undefined') {
        const originalGenerateId = window.game.generateId;
        window.game.generateId = function() {
            // Используем player_id из authManager если доступен
            if (authManager.currentUser && authManager.currentUser.player_id) {
                return authManager.currentUser.player_id;
            }
            // Иначе генерируем временный ID
            return originalGenerateId ? originalGenerateId.call(this) : 'temp_' + Math.random().toString(36).substring(2, 15);
        };
        
        // Обновляем connectWebSocket для передачи токена
        const originalConnectWebSocket = window.game.connectWebSocket;
        window.game.connectWebSocket = function() {
            if (this.ws) {
                try {
                    this.ws.close();
                } catch (e) {
                    console.warn('Error closing existing WebSocket:', e);
                }
            }
            
            if (!this.roomId || !this.playerId) {
                console.error('Cannot connect: missing roomId or playerId', { roomId: this.roomId, playerId: this.playerId });
                return;
            }
            
            // Получаем токен из authManager
            let token = null;
            if (typeof authManager !== 'undefined') {
                token = authManager.getAccessToken();
            }
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            let wsUrl = `${protocol}//${window.location.host}/ws/${this.roomId}/${this.playerId}`;
            
            // Добавляем токен в query параметры если доступен
            if (token) {
                wsUrl += `?token=${encodeURIComponent(token)}`;
            }
            
            console.log(`Connecting to WebSocket: ${wsUrl}`);
            this.ws = new WebSocket(wsUrl);
            
            // Используем оригинальные обработчики из v2.7
            if (originalConnectWebSocket) {
                // Сохраняем оригинальные обработчики
                const originalOnOpen = this.ws.onopen;
                const originalOnMessage = this.ws.onmessage;
                const originalOnClose = this.ws.onclose;
                const originalOnError = this.ws.onerror;
                
                this.ws.onopen = () => {
                    console.log(`WebSocket: Connected to room ${this.roomId}, playerId=${this.playerId}`);
                    document.getElementById('status').textContent = 'Подключено. Ожидание противника...';
                    this.updateConnectionStatus(true);
                    this.reconnectAttempts = 0;
                    this.isReconnecting = false;
                    this.showScreen('game-screen');
                    setTimeout(() => this.hideSwitchersPanel(), 10);
                };
                
                this.ws.onmessage = (e) => {
                    try {
                        const data = JSON.parse(e.data);
                        console.log('WebSocket: Received message:', data.type, data);
                        this.handleServerMessage(data);
                    } catch (error) {
                        console.error('WebSocket: Error parsing message:', error, e.data);
                    }
                };
                
                this.ws.onclose = (event) => {
                    console.log(`WebSocket: Closed, code=${event.code}, reason=${event.reason || 'none'}, wasClean=${event.wasClean}`);
                    this.updateConnectionStatus(false);
                    
                    if (event.code === 4000) {
                        console.error(`WebSocket: Connection rejected - ${event.reason}`);
                        const statusEl = document.getElementById('status');
                        if (statusEl) {
                            statusEl.textContent = `Ошибка подключения: ${event.reason || 'Неверные параметры'}`;
                        }
                        this.playerId = this.generateId();
                        console.log(`Generated new playerId: ${this.playerId}`);
                        if (this.reconnectAttempts < this.maxReconnectAttempts) {
                            setTimeout(() => this.connectWebSocket(), 1000);
                        }
                        return;
                    }
                    
                    if (!this.isReconnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
                        console.log(`WebSocket: Attempting reconnect ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts}`);
                        this.attemptReconnect();
                    } else {
                        console.log(`WebSocket: Max reconnects reached or not reconnecting`);
                        const statusEl = document.getElementById('status');
                        if (statusEl) {
                            statusEl.textContent = 'Отключено';
                        }
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error(`WebSocket: Error occurred`, error);
                    this.updateConnectionStatus(false);
                    const statusEl = document.getElementById('status');
                    if (statusEl) {
                        statusEl.textContent = 'Ошибка подключения';
                    }
                    if (!this.isReconnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
                        setTimeout(() => this.attemptReconnect(), 1000);
                    }
                };
            }
        };
        
        // Обновляем playerId при инициализации
        if (authManager.currentUser && authManager.currentUser.player_id) {
            window.game.playerId = authManager.currentUser.player_id;
        }
        
        console.log('v2.8 updates applied to game.js');
    }
}

function initBasicGame() {
    // Базовая инициализация если v2.7 не загружен
    console.log('Используется базовая версия игры');
    // Минимальная функциональность будет доступна
}

