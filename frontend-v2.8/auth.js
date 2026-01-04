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
            });
        }
    }
    
    /**
     * Регистрация нового пользователя
     */
    async register(username, email, password) {
        try {
            const response = await fetch(`${this.baseURL}/api/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, email, password }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка регистрации');
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
     * Получение токена для WebSocket соединений
     */
    getWebSocketToken() {
        return this.accessToken;
    }
}

// Глобальный экземпляр
const authManager = new AuthManager();

