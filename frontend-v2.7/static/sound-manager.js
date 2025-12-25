// sound-manager.js - Класс для управления звуками
class SoundManager {
    constructor() {
        this.enabled = localStorage.getItem('chess_sound_enabled') !== 'false';
        this.volume = parseFloat(localStorage.getItem('chess_sound_volume') || '0.5');
        this.sounds = {};
        this.initSounds();
        this.initControls();
    }
    
    initSounds() {
        // Создаём звуки программно (в реальном приложении загружаем файлы)
        const soundPaths = {
            move: '/v2.7/static/sounds/move.mp3',
            capture: '/v2.7/static/sounds/capture.mp3',
            check: '/v2.7/static/sounds/check.mp3',
            checkmate: '/v2.7/static/sounds/checkmate.mp3',
            promotion: '/v2.7/static/sounds/promotion.mp3',
            draw: '/v2.7/static/sounds/draw.mp3'
        };
        
        Object.entries(soundPaths).forEach(([name, path]) => {
            const audio = new Audio();
            audio.preload = 'auto';
            audio.volume = this.volume;
            // В реальном приложении: audio.src = path;
            this.sounds[name] = audio;
        });
    }
    
    initControls() {
        const toggleBtn = document.getElementById('sound-toggle');
        const volumeSlider = document.getElementById('volume-slider');
        
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
            this.updateToggleButton();
        }
        
        if (volumeSlider) {
            volumeSlider.addEventListener('input', (e) => {
                this.setVolume(e.target.value / 100);
            });
            volumeSlider.value = this.volume * 100;
        }
    }
    
    play(soundName) {
        if (!this.enabled || !this.sounds[soundName]) return;
        
        const sound = this.sounds[soundName].cloneNode();
        sound.volume = this.volume;
        sound.play().catch(() => {}); // Игнорируем ошибки автоплея
    }
    
    toggle() {
        this.enabled = !this.enabled;
        localStorage.setItem('chess_sound_enabled', this.enabled);
        this.updateToggleButton();
    }
    
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        localStorage.setItem('chess_sound_volume', this.volume);
        Object.values(this.sounds).forEach(sound => {
            sound.volume = this.volume;
        });
    }
    
    updateToggleButton() {
        const btn = document.getElementById('sound-toggle');
        if (btn) {
            btn.textContent = this.enabled ? '🔊' : '🔇';
        }
    }
}

