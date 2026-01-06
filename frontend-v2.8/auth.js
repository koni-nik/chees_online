/**
 * Модуль аутентификации для Chess Online v2.8
 */
class AuthManager {
    constructor() {
        this.baseURL = window.location.origin;
        this.accessToken = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
        this.currentUser = null;
        
        // Проверяем токен при инициализации
        if (this.accessToken) {
            this.getCurrentUser().catch(() => {
                // Если токен недействителен, очищаем
                this.logout();
                // Пытаемся восстановить гостевой режим
                this.restoreGuest();
            });
        } else {
            // Если нет токена, пытаемся восстановить гостевой режим
            this.restoreGuest();
        }
        
        // Сохраняем ссылку на authManager в window для отладки
        if (typeof window !== 'undefined') {
            window.authManager = this;
        }
    }
    
    /**
     * Регистрация нового пользователя
     */
    async register(username, email, password) {
        try {
            console.log('Попытка регистрации:', username, email);
            const response = await fetch(`${this.baseURL}/api/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, email, password }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                const errorMsg = data.detail || data.error || 'Ошибка регистрации';
                console.error('Ошибка регистрации:', errorMsg);
                throw new Error(errorMsg);
            }
            
            // Сохраняем токены
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('access_token', this.accessToken);
            localStorage.setItem('refresh_token', this.refreshToken);
            
            // Получаем данные пользователя
            await this.getCurrentUser();
            
            console.log('Регистрация успешна, пользователь:', this.currentUser);
            return { success: true, user: this.currentUser };
        } catch (error) {
            console.error('Ошибка при регистрации:', error);
            return { success: false, error: error.message || 'Ошибка регистрации' };
        }
    }
    
    /**
     * Вход в систему
     */
    async login(email, password) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка входа');
            }
            
            // Сохраняем токены
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('access_token', this.accessToken);
            localStorage.setItem('refresh_token', this.refreshToken);
            
            // Получаем данные пользователя
            await this.getCurrentUser();
            
            return { success: true, user: this.currentUser };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
    
    /**
     * Выход из системы
     */
    async logout() {
        try {
            if (this.refreshToken) {
                await fetch(`${this.baseURL}/api/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.accessToken}`,
                    },
                    body: JSON.stringify({ refresh_token: this.refreshToken }),
                });
            }
        } catch (error) {
            console.error('Ошибка при выходе:', error);
        } finally {
            this.accessToken = null;
            this.refreshToken = null;
            this.currentUser = null;
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
        }
    }
    
    /**
     * Обновление access token
     */
    async refreshAccessToken() {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: this.refreshToken }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error('Ошибка обновления токена');
            }
            
            this.accessToken = data.access_token;
            localStorage.setItem('access_token', this.accessToken);
            
            return true;
        } catch (error) {
            this.logout();
            return false;
        }
    }
    
    /**
     * Получение текущего пользователя
     */
    async getCurrentUser() {
        if (!this.accessToken) {
            return null;
        }
        
        try {
            const response = await fetch(`${this.baseURL}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`,
                },
            });
            
            if (response.status === 401) {
                // Токен истёк, пытаемся обновить
                if (await this.refreshAccessToken()) {
                    return await this.getCurrentUser();
                }
                return null;
            }
            
            if (!response.ok) {
                throw new Error('Ошибка получения данных пользователя');
            }
            
            const data = await response.json();
            this.currentUser = data;
            return data;
        } catch (error) {
            console.error('Ошибка получения пользователя:', error);
            return null;
        }
    }
    
    /**
     * Верификация email
     */
    async verifyEmail(token) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/verify-email?token=${token}`, {
                method: 'GET',
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Ошибка верификации');
            }
            
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
    
    /**
     * Запрос сброса пароля
     */
    async forgotPassword(email) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/forgot-password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email }),
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Ошибка запроса сброса пароля');
            }
            
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
    
    /**
     * Сброс пароля по токену
     */
    async resetPassword(token, newPassword) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/reset-password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ token, new_password: newPassword }),
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Ошибка сброса пароля');
            }
            
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
    
    /**
     * Проверка, авторизован ли пользователь
     */
    isAuthenticated() {
        return !!this.accessToken && !!this.currentUser;
    }
    
    /**
     * Вход как гость (без регистрации)
     */
    async loginAsGuest() {
        try {
            console.log('Начало входа как гость...');
            
            // Генерируем случайный ID для гостя
            const guestId = 'guest_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
            const shortId = guestId.substring(6, 12);
            
            // Создаем временного пользователя-гостя
            this.currentUser = {
                player_id: guestId,
                username: `Гость_${shortId}`,
                email: `${guestId}@guest.local`,
                is_guest: true
            };
            
            // Сохраняем информацию о госте в localStorage
            localStorage.setItem('guest_id', guestId);
            localStorage.setItem('guest_username', this.currentUser.username);
            
            // Очищаем токены (гость не использует токены)
            this.accessToken = null;
            this.refreshToken = null;
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            
            console.log('Вход как гость успешен:', this.currentUser);
            return { success: true, user: this.currentUser };
        } catch (error) {
            console.error('Ошибка входа как гость:', error);
            return { success: false, error: error.message || 'Неизвестная ошибка' };
        }
    }
    
    /**
     * Проверка, является ли пользователь гостем
     */
    isGuest() {
        return this.currentUser && this.currentUser.is_guest === true;
    }
    
    /**
     * Восстановление гостевого режима из localStorage
     */
    restoreGuest() {
        const guestId = localStorage.getItem('guest_id');
        const guestUsername = localStorage.getItem('guest_username');
        
        if (guestId && guestUsername) {
            this.currentUser = {
                player_id: guestId,
                username: guestUsername,
                email: `${guestId}@guest.local`,
                is_guest: true
            };
            return true;
        }
        return false;
    }
    
    /**
     * Получение токена для WebSocket соединений
     */
    getWebSocketToken() {
        return this.accessToken;
    }
    
    /**
     * Получение player_id для использования в игре
     */
    getPlayerId() {
        if (this.currentUser && this.currentUser.player_id) {
            return this.currentUser.player_id;
        }
        // Если нет пользователя, генерируем временный ID
        const tempId = 'temp_' + Math.random().toString(36).substring(2, 15);
        return tempId;
    }
    
    /**
     * Получение access токена для WebSocket соединений
     */
    getAccessToken() {
        return this.accessToken;
    }
}

// Глобальный экземпляр
const authManager = new AuthManager();

