// game.js - Шахматы v2.5 с Neon темой и новыми функциями
class ChessGame {
    constructor() {
        this.canvas = document.getElementById('board');
        this.ctx = this.canvas.getContext('2d');
        this.cellSize = 60;
        this.board = null;
        this.selectedPiece = null;
        this.validMoves = [];
        this.validAttacks = [];
        this.myColor = null;
        this.currentPlayer = 'white';
        this.ws = null;
        this.roomId = null;
        this.lastMove = null; // Для подсветки последнего хода
        this.moveHistory = []; // История ходов
        
        // Таймеры (в секундах)
        this.timers = { white: 600, black: 600 };
        this.timerInterval = null;
        this.playerId = this.generateId();
        this.isLocalGame = false;
        
        // Reconnect
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.isReconnecting = false;
        
        // Темы для canvas
        this.themes = {
            neon: {
                boardLight: '#2a2a3a',
                boardDark: '#1a1a25',
                selected: 'rgba(0, 255, 136, 0.4)',
                highlightMove: 'rgba(0, 255, 247, 0.4)',
                highlightAttack: 'rgba(255, 0, 255, 0.4)',
                lastMove: 'rgba(168, 85, 247, 0.4)',
                white: '#e0e0e0',
                black: '#1a1a1a',
                crown: '#ffd700',
                outline: { white: '#000', black: '#00fff7' },
                coords: 'rgba(255, 255, 255, 0.3)',
                pieceGlow: true
            },
            classic: {
                boardLight: 'rgb(80, 80, 110)',
                boardDark: 'rgb(45, 45, 65)',
                selected: 'rgba(100, 80, 130, 0.7)',
                highlightMove: 'rgba(90, 90, 140, 0.6)',
                highlightAttack: 'rgba(150, 70, 100, 0.6)',
                lastMove: 'rgba(100, 80, 130, 0.5)',
                white: 'rgb(169, 169, 169)',
                black: 'rgb(40, 40, 40)',
                crown: 'rgb(255, 215, 0)',
                outline: { white: 'rgb(0, 0, 0)', black: 'rgb(255, 255, 255)' },
                coords: 'rgba(255, 255, 255, 0.3)',
                pieceGlow: false
            }
        };
        
        const savedTheme = localStorage.getItem('chess_theme_v2') || 'neon';
        this.colors = this.themes[savedTheme];
        
        this.devPanelOpen = false;
        this.stats = this.loadStats();
        
        // Кастомные ходы и карточки
        this.customMoves = { white: {}, black: {} };
        this.abilityCards = { white: {}, black: {} };
        this.loadCustomMoves();
        
        // Move Board
        this.moveBoardOpen = false;
        this.mbCanvas = document.getElementById('move-board-canvas');
        this.mbCtx = this.mbCanvas.getContext('2d');
        this.mbCellSize = 40;
        this.mbPieceTypes = ['pawn', 'rook', 'knight', 'bishop', 'queen', 'king'];
        this.mbPieceIndex = 0;
        this.mbColor = 'white';
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
        
        // Создание карточки
        this.cardCreationMode = false;
        this.newCardData = { name: '', color: 'white', moves: [], attacks: [] };
        
        // Чат
        this.chatOpen = true;
        
        this.initMenuListeners();
        this.initBoard();
        
        // Проверяем, не открыт ли уже экран игры при загрузке
        this.checkGameScreenVisibility();
    }
    
    checkGameScreenVisibility() {
        const gameScreen = document.getElementById('game-screen');
        if (gameScreen && !gameScreen.classList.contains('hidden')) {
            this.hideSwitchersPanel();
        }
    }
    
    generateId() { return Math.random().toString(36).substring(2, 10); }
    
    // ============ СОХРАНЕНИЕ/ЗАГРУЗКА ============
    loadStats() {
        const saved = localStorage.getItem('chess_stats_v2');
        return saved ? JSON.parse(saved) : { total: 0, white: 0, black: 0, draws: 0 };
    }
    
    saveStats() { localStorage.setItem('chess_stats_v2', JSON.stringify(this.stats)); }
    
    loadCustomMoves() {
        const saved = localStorage.getItem('chess_custom_moves_v2');
        if (saved) {
            const data = JSON.parse(saved);
            this.customMoves = data.moves || { white: {}, black: {} };
            this.abilityCards = data.cards || { white: {}, black: {} };
        }
        this.updateCardList();
    }
    
    saveCustomMoves() {
        const data = { moves: this.customMoves, cards: this.abilityCards };
        localStorage.setItem('chess_custom_moves_v2', JSON.stringify(data));
        this.setDevStatus('Saved!');
    }
    
    // ============ МЕНЮ ============
    initMenuListeners() {
        document.getElementById('btn-online').addEventListener('click', () => this.showScreen('room-screen'));
        document.getElementById('btn-local').addEventListener('click', () => this.startLocalGame());
        document.getElementById('btn-stats').addEventListener('click', () => this.showStatsScreen());
        
        document.getElementById('btn-join').addEventListener('click', () => {
            this.joinRoom(document.getElementById('room-input').value || this.generateId());
        });
        document.getElementById('btn-create').addEventListener('click', () => this.joinRoom(this.generateId()));
        document.getElementById('btn-back-room').addEventListener('click', () => this.showScreen('main-menu'));
        document.getElementById('btn-back-stats').addEventListener('click', () => this.showScreen('main-menu'));
        
        document.getElementById('resign').addEventListener('click', () => {
            if (this.isLocalGame) {
                this.showGameOver(this.currentPlayer === 'white' ? 'Black' : 'White', 'resignation');
            } else if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'resign' }));
            }
        });
        
        document.getElementById('btn-to-menu').addEventListener('click', () => {
            if (this.ws) this.ws.close();
            this.showScreen('main-menu');
        });
        
        document.getElementById('play-again').addEventListener('click', () => {
            document.getElementById('game-over-modal').classList.add('hidden');
            if (this.isLocalGame) this.startLocalGame();
            else this.joinRoom(this.generateId());
        });
        
        document.getElementById('to-menu-modal').addEventListener('click', () => {
            document.getElementById('game-over-modal').classList.add('hidden');
            if (this.ws) this.ws.close();
            this.showScreen('main-menu');
        });
        
        // Копирование ссылки
        document.getElementById('copy-room-btn').addEventListener('click', () => this.copyRoomLink());
        
        // Предложение ничьей
        document.getElementById('offer-draw').addEventListener('click', () => this.offerDraw());
        document.getElementById('accept-draw').addEventListener('click', () => this.respondToDraw(true));
        document.getElementById('decline-draw').addEventListener('click', () => this.respondToDraw(false));
        
        // Чат
        document.getElementById('chat-toggle').addEventListener('click', () => this.toggleChat());
        document.getElementById('chat-send').addEventListener('click', () => this.sendChatMessage());
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendChatMessage();
        });
        
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        this.canvas.addEventListener('contextmenu', (e) => { e.preventDefault(); this.handleClick(e, true); });
        
        // Touch события для мобильных
        this.canvas.addEventListener('touchstart', (e) => this.handleTouch(e));
        
        this.initDevPanel();
        this.initMoveBoard();
    }
    
    handleKeyDown(e) {
        if (e.key === 'd' || e.key === 'D' || e.key === 'в' || e.key === 'В') {
            if (!this.cardCreationMode) this.toggleDevPanel();
        }
        
        if (this.cardCreationMode) {
            if (e.key === 'Enter') {
                this.saveCard();
            } else if (e.key === 'Tab') {
                e.preventDefault();
                this.newCardData.color = this.newCardData.color === 'white' ? 'black' : 'white';
                this.mbColor = this.newCardData.color;
                document.getElementById('card-color-display').textContent = this.newCardData.color;
                this.updateMbColorButton();
                this.drawMoveBoard();
            } else if (e.key === 'Escape') {
                this.cancelCardCreation();
            }
        } else if (e.key === 'Escape') {
            if (this.moveBoardOpen) this.closeMoveBoard();
            else if (this.devPanelOpen) this.toggleDevPanel();
        }
    }
    
    showScreen(screenId) {
        document.querySelectorAll('.menu-screen, #game-screen').forEach(el => el.classList.add('hidden'));
        const targetScreen = document.getElementById(screenId);
        if (targetScreen) {
            targetScreen.classList.remove('hidden');
        }
        
        // Скрываем переключатель версий во время игры
        // Используем setTimeout для гарантии, что DOM обновлен
        setTimeout(() => {
            if (screenId === 'game-screen') {
                this.hideSwitchersPanel();
            } else {
                this.showSwitchersPanel();
            }
        }, 0);
    }
    
    hideSwitchersPanel() {
        const switchersPanel = document.querySelector('.switchers-panel');
        if (switchersPanel) {
            document.body.classList.add('game-active');
            switchersPanel.classList.add('hidden-in-game');
            switchersPanel.style.display = 'none';
            switchersPanel.style.visibility = 'hidden';
            switchersPanel.style.opacity = '0';
            switchersPanel.style.pointerEvents = 'none';
            switchersPanel.style.zIndex = '-1';
        }
    }
    
    showSwitchersPanel() {
        const switchersPanel = document.querySelector('.switchers-panel');
        if (switchersPanel) {
            document.body.classList.remove('game-active');
            switchersPanel.classList.remove('hidden-in-game');
            switchersPanel.style.display = '';
            switchersPanel.style.visibility = '';
            switchersPanel.style.opacity = '';
            switchersPanel.style.pointerEvents = '';
            switchersPanel.style.zIndex = '';
        }
    }
    
    showStatsScreen() {
        document.getElementById('stat-total').textContent = this.stats.total;
        document.getElementById('stat-white').textContent = this.stats.white;
        document.getElementById('stat-black').textContent = this.stats.black;
        document.getElementById('stat-draws').textContent = this.stats.draws;
        
        if (this.stats.total > 0) {
            const whitePct = (this.stats.white / this.stats.total * 100).toFixed(1);
            const blackPct = (this.stats.black / this.stats.total * 100).toFixed(1);
            document.getElementById('bar-white').style.width = whitePct + '%';
            document.getElementById('bar-black').style.width = blackPct + '%';
            document.getElementById('stats-percent').textContent = `Белые: ${whitePct}%  |  Чёрные: ${blackPct}%`;
        }
        this.showScreen('stats-screen');
    }
    
    startLocalGame() {
        this.isLocalGame = true;
        this.myColor = 'white';
        this.currentPlayer = 'white';
        this.board = this.getInitialBoard();
        this.timers = { white: 600, black: 600 };
        this.lastMove = null;
        this.moveHistory = [];
        this.updateMoveHistoryDisplay();
        this.startTimer();
        this.selectedPiece = null;
        this.validMoves = [];
        this.validAttacks = [];
        
        document.getElementById('my-color').textContent = 'Белые / Чёрные';
        document.getElementById('status').textContent = 'Локальная игра';
        document.getElementById('current-room').textContent = 'Локально';
        this.updateTurnIndicator();
        this.updateConnectionStatus(true);
        this.showScreen('game-screen');
        // Дополнительный вызов для гарантии
        setTimeout(() => this.hideSwitchersPanel(), 10);
        this.draw();
    }
    
    // ============ КОПИРОВАНИЕ ССЫЛКИ ============
    copyRoomLink() {
        const url = `${window.location.origin}/v2.5?room=${this.roomId}`;
        navigator.clipboard.writeText(url).then(() => {
            const btn = document.getElementById('copy-room-btn');
            btn.textContent = '✓';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = 'Копировать';
                btn.classList.remove('copied');
            }, 2000);
        });
    }
    
    // ============ ЧАТ ============
    toggleChat() {
        this.chatOpen = !this.chatOpen;
        document.getElementById('chat-body').style.display = this.chatOpen ? 'block' : 'none';
        document.querySelector('.chat-toggle').textContent = this.chatOpen ? '▼' : '▲';
    }
    
    sendChatMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message) return;
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'chat', message }));
        }
        
        this.addChatMessage('You', message);
        input.value = '';
    }
    
    addChatMessage(sender, message, isSystem = false) {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'chat-message' + (isSystem ? ' system' : '');
        
        if (isSystem) {
            div.textContent = message;
        } else {
            div.innerHTML = `<span class="sender">${sender}:</span> ${message}`;
        }
        
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }
    
    // Русские названия фигур
    getPieceNameRu(type) {
        return { king: 'Король', queen: 'Ферзь', rook: 'Ладья', bishop: 'Слон', knight: 'Конь', pawn: 'Пешка' }[type] || type;
    }
    
    // ============ НИЧЬЯ ============
    offerDraw() {
        if (this.isLocalGame) return;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'offer_draw' }));
            this.addChatMessage(null, 'Вы предложили ничью', true);
        }
    }
    
    respondToDraw(accept) {
        document.getElementById('draw-offer-modal').classList.add('hidden');
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'draw_response', accept }));
        }
    }
    
    showDrawOffer() {
        document.getElementById('draw-offer-modal').classList.remove('hidden');
    }
    
    // ============ ИСТОРИЯ ХОДОВ ============
    addMoveToHistory(from, to, piece, captured) {
        const files = 'abcdefgh';
        const fromNotation = files[from[0]] + (8 - from[1]);
        const toNotation = files[to[0]] + (8 - to[1]);
        
        const pieceSymbols = { king: 'K', queen: 'Q', rook: 'R', bishop: 'B', knight: 'N', pawn: '' };
        const symbol = pieceSymbols[piece.type] || '';
        const capture = captured ? 'x' : '-';
        
        const notation = symbol + fromNotation + capture + toNotation;
        
        if (piece.color === 'white') {
            this.moveHistory.push({ number: this.moveHistory.length + 1, white: notation, black: '' });
        } else {
            if (this.moveHistory.length > 0) {
                this.moveHistory[this.moveHistory.length - 1].black = notation;
            }
        }
        
        this.updateMoveHistoryDisplay();
    }
    
    updateMoveHistoryDisplay() {
        const container = document.getElementById('move-history-list');
        container.innerHTML = '';
        
        this.moveHistory.forEach(move => {
            container.innerHTML += `
                <span class="move-number">${move.number}.</span>
                <span class="move-white">${move.white}</span>
                <span class="move-black">${move.black}</span>
            `;
        });
        
        container.scrollTop = container.scrollHeight;
    }
    
    // ============ ИНДИКАТОР СОЕДИНЕНИЯ ============
    updateConnectionStatus(connected) {
        const dot = document.getElementById('connection-dot');
        const text = document.getElementById('connection-text');
        
        if (connected) {
            dot.classList.remove('disconnected');
            text.textContent = 'Подключено';
        } else {
            dot.classList.add('disconnected');
            text.textContent = this.isReconnecting ? 'Переподключение...' : 'Отключено';
        }
    }
    
    // ============ ПАНЕЛЬ РАЗРАБОТЧИКА ============
    initDevPanel() {
        document.getElementById('dev-close').addEventListener('click', () => this.toggleDevPanel());
        document.getElementById('apply-time').addEventListener('click', () => this.applyTime());
        document.getElementById('reset-moves').addEventListener('click', () => this.resetCustomMoves());
        document.getElementById('deselect-btn').addEventListener('click', () => this.deselectPiece());
        document.getElementById('new-card-btn').addEventListener('click', () => this.startCardCreation());
        document.getElementById('open-board-btn').addEventListener('click', () => this.toggleMoveBoard());
        document.getElementById('save-all-btn').addEventListener('click', () => this.saveCustomMoves());
        document.getElementById('close-panel-btn').addEventListener('click', () => this.toggleDevPanel());
        
        this.initDevPanelDrag();
    }
    
    toggleDevPanel() {
        this.devPanelOpen = !this.devPanelOpen;
        document.getElementById('dev-panel').classList.toggle('open', this.devPanelOpen);
        if (!this.devPanelOpen) {
            this.closeMoveBoard();
            this.cancelCardCreation();
        }
    }
    
    initDevPanelDrag() {
        const panel = document.getElementById('dev-panel');
        const header = panel.querySelector('.dev-panel-header');
        let isDragging = false, offsetX, offsetY;
        
        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            offsetX = e.clientX - panel.offsetLeft;
            offsetY = e.clientY - panel.offsetTop;
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                panel.style.left = (e.clientX - offsetX) + 'px';
                panel.style.top = (e.clientY - offsetY) + 'px';
                panel.style.right = 'auto';
            }
        });
        
        document.addEventListener('mouseup', () => isDragging = false);
    }
    
    setDevStatus(text) { document.getElementById('dev-status').textContent = text; }
    
    applyTime() {
        const whiteTime = parseInt(document.getElementById('white-time').value) || 10;
        const blackTime = parseInt(document.getElementById('black-time').value) || 10;
        this.timers.white = whiteTime * 60;
        this.timers.black = blackTime * 60;
        this.updateTimerDisplay();
        this.setDevStatus(`Time: W=${whiteTime}m B=${blackTime}m`);
    }
    
    resetCustomMoves() {
        if (!this.isLocalGame && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'reset_custom_moves' }));
        } else {
            this.customMoves = { white: {}, black: {} };
            this.abilityCards = { white: {}, black: {} };
            this.saveCustomMoves();
            this.updateCardList();
        }
        this.setDevStatus('All moves reset');
    }
    
    deselectPiece() {
        this.selectedPiece = null;
        this.validMoves = [];
        this.validAttacks = [];
        document.getElementById('selected-piece-info').textContent = 'None';
        this.draw();
    }
    
    // ============ КАРТОЧКИ СПОСОБНОСТЕЙ ============
    startCardCreation() {
        this.cardCreationMode = true;
        this.newCardData = { name: '', color: 'white', moves: [], attacks: [] };
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
        this.mbColor = 'white';
        
        document.getElementById('card-form').classList.remove('hidden');
        document.getElementById('card-name-input').value = '';
        document.getElementById('card-name-input').focus();
        document.getElementById('card-color-display').textContent = 'white';
        document.getElementById('card-moves-count').textContent = '0';
        document.getElementById('card-attacks-count').textContent = '0';
        
        this.openMoveBoard();
        this.setDevStatus('Enter card name...');
    }
    
    saveCard() {
        const name = document.getElementById('card-name-input').value.trim();
        if (!name) {
            this.setDevStatus('Enter name!');
            return;
        }
        
        const pieceType = this.mbPieceTypes[this.mbPieceIndex];
        const color = this.newCardData.color;
        
        this.abilityCards[color][name] = {
            pieceType: pieceType,
            moves: [...this.mbAddedMoves],
            attacks: [...this.mbAddedAttacks],
            color: this.getRandomCardColor()
        };
        
        if (!this.customMoves[color][pieceType]) {
            this.customMoves[color][pieceType] = { moves: [], attacks: [] };
        }
        
        this.mbAddedMoves.forEach(move => {
            const existing = this.customMoves[color][pieceType].moves;
            if (!existing.some(m => m[0] === move[0] && m[1] === move[1])) {
                existing.push(move);
            }
        });
        
        this.mbAddedAttacks.forEach(attack => {
            const existing = this.customMoves[color][pieceType].attacks;
            if (!existing.some(a => a[0] === attack[0] && a[1] === attack[1])) {
                existing.push(attack);
            }
        });
        
        if (!this.isLocalGame && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'save_card',
                color: color,
                name: name,
                card_data: this.abilityCards[color][name]
            }));
            this.updateCardList();
        } else {
            this.saveCustomMoves();
            this.updateCardList();
        }
        
        this.cancelCardCreation();
        this.setDevStatus(`Card "${name}" saved`);
    }
    
    getRandomCardColor() {
        const colors = [[0, 255, 247], [255, 0, 255], [168, 85, 247], [0, 255, 136], [255, 107, 0]];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    cancelCardCreation() {
        this.cardCreationMode = false;
        document.getElementById('card-form').classList.add('hidden');
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
    }
    
    updateCardList() {
        const list = document.getElementById('card-list');
        list.innerHTML = '';
        
        ['white', 'black'].forEach(color => {
            Object.entries(this.abilityCards[color] || {}).forEach(([name, data]) => {
                const item = document.createElement('div');
                item.className = 'card-item' + (data.enabled === false ? ' disabled' : '');
                
                const cardColor = data.color || [0, 255, 247];
                const colorBar = document.createElement('div');
                colorBar.className = 'card-color-bar';
                colorBar.style.background = `rgb(${cardColor.join(',')})`;
                colorBar.style.boxShadow = `0 0 10px rgba(${cardColor.join(',')}, 0.5)`;
                
                const info = document.createElement('div');
                info.className = 'card-info';
                info.innerHTML = `
                    <div class="card-name">${name}</div>
                    <div class="card-details">${color} ${data.pieceType || ''} | ${data.moves?.length || 0}M/${data.attacks?.length || 0}A</div>
                `;
                
                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'card-toggle';
                toggleBtn.textContent = data.enabled === false ? '○' : '●';
                toggleBtn.title = data.enabled === false ? 'Enable' : 'Disable';
                toggleBtn.onclick = (e) => { e.stopPropagation(); this.toggleCard(color, name); };
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'card-delete';
                deleteBtn.textContent = '×';
                deleteBtn.onclick = (e) => { e.stopPropagation(); this.deleteCard(color, name); };
                
                item.appendChild(colorBar);
                item.appendChild(info);
                item.appendChild(toggleBtn);
                item.appendChild(deleteBtn);
                list.appendChild(item);
            });
        });
    }
    
    toggleCard(color, name) {
        const card = this.abilityCards[color][name];
        if (!card) return;
        
        card.enabled = (card.enabled === true || card.enabled === undefined) ? false : true;
        
        if (!this.isLocalGame && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'toggle_card',
                color: color,
                name: name,
                enabled: card.enabled
            }));
        } else {
            this.rebuildCustomMoves();
            this.saveCustomMoves();
        }
        this.updateCardList();
        this.setDevStatus(`Card "${name}" ${card.enabled ? 'enabled' : 'disabled'}`);
    }
    
    rebuildCustomMoves() {
        this.customMoves = { white: {}, black: {} };
        ['white', 'black'].forEach(color => {
            Object.entries(this.abilityCards[color] || {}).forEach(([name, data]) => {
                if (data.enabled === false) return;
                const pieceType = data.pieceType;
                if (!this.customMoves[color][pieceType]) {
                    this.customMoves[color][pieceType] = { moves: [], attacks: [] };
                }
                (data.moves || []).forEach(move => {
                    if (!this.customMoves[color][pieceType].moves.some(m => m[0] === move[0] && m[1] === move[1])) {
                        this.customMoves[color][pieceType].moves.push(move);
                    }
                });
                (data.attacks || []).forEach(attack => {
                    if (!this.customMoves[color][pieceType].attacks.some(a => a[0] === attack[0] && a[1] === attack[1])) {
                        this.customMoves[color][pieceType].attacks.push(attack);
                    }
                });
            });
        });
    }
    
    deleteCard(color, name) {
        const card = this.abilityCards[color][name];
        if (card) {
            const pieceType = card.pieceType;
            const custom = this.customMoves[color]?.[pieceType];
            
            if (custom) {
                card.moves?.forEach(move => {
                    if (custom.moves) {
                        custom.moves = custom.moves.filter(m => !(m[0] === move[0] && m[1] === move[1]));
                    }
                });
                card.attacks?.forEach(attack => {
                    if (custom.attacks) {
                        custom.attacks = custom.attacks.filter(a => !(a[0] === attack[0] && a[1] === attack[1]));
                    }
                });
            }
        }
        
        if (!this.isLocalGame && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'delete_card',
                color: color,
                name: name
            }));
        } else {
            delete this.abilityCards[color][name];
            this.saveCustomMoves();
            this.updateCardList();
        }
        this.setDevStatus(`Card "${name}" deleted`);
    }
    
    // ============ MOVE BOARD ============
    initMoveBoard() {
        document.getElementById('mb-prev').addEventListener('click', () => this.mbPrevPiece());
        document.getElementById('mb-next').addEventListener('click', () => this.mbNextPiece());
        document.getElementById('mb-color').addEventListener('click', () => this.mbToggleColor());
        document.getElementById('mb-close').addEventListener('click', () => this.closeMoveBoard());
        
        this.mbCanvas.addEventListener('click', (e) => this.handleMbClick(e, false));
        this.mbCanvas.addEventListener('contextmenu', (e) => { e.preventDefault(); this.handleMbClick(e, true); });
    }
    
    toggleMoveBoard() {
        if (this.moveBoardOpen) this.closeMoveBoard();
        else this.openMoveBoard();
    }
    
    openMoveBoard() {
        this.moveBoardOpen = true;
        document.getElementById('move-board').classList.remove('hidden');
        this.updateMbPieceName();
        this.updateMbColorButton();
        this.drawMoveBoard();
    }
    
    closeMoveBoard() {
        this.moveBoardOpen = false;
        document.getElementById('move-board').classList.add('hidden');
    }
    
    mbPrevPiece() {
        this.mbPieceIndex = (this.mbPieceIndex - 1 + this.mbPieceTypes.length) % this.mbPieceTypes.length;
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
        this.updateMbPieceName();
        this.updateMbStats();
        this.drawMoveBoard();
    }
    
    mbNextPiece() {
        this.mbPieceIndex = (this.mbPieceIndex + 1) % this.mbPieceTypes.length;
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
        this.updateMbPieceName();
        this.updateMbStats();
        this.drawMoveBoard();
    }
    
    mbToggleColor() {
        this.mbColor = this.mbColor === 'white' ? 'black' : 'white';
        if (this.cardCreationMode) {
            this.newCardData.color = this.mbColor;
            document.getElementById('card-color-display').textContent = this.mbColor;
        }
        this.mbAddedMoves = [];
        this.mbAddedAttacks = [];
        this.updateMbColorButton();
        this.updateMbStats();
        this.drawMoveBoard();
    }
    
    updateMbPieceName() {
        document.getElementById('mb-piece-name').textContent = this.mbPieceTypes[this.mbPieceIndex].toUpperCase();
    }
    
    updateMbColorButton() {
        const btn = document.getElementById('mb-color');
        btn.textContent = this.mbColor;
        btn.style.background = this.mbColor === 'white' ? '#e0e0e0' : '#1a1a1a';
        btn.style.color = this.mbColor === 'white' ? '#000' : '#00fff7';
        btn.style.border = this.mbColor === 'white' ? 'none' : '1px solid #00fff7';
    }
    
    updateMbStats() {
        document.getElementById('mb-stats').textContent = `Added: ${this.mbAddedMoves.length} moves, ${this.mbAddedAttacks.length} attacks`;
        if (this.cardCreationMode) {
            document.getElementById('card-moves-count').textContent = this.mbAddedMoves.length;
            document.getElementById('card-attacks-count').textContent = this.mbAddedAttacks.length;
        }
    }
    
    handleMbClick(e, isAttack) {
        const rect = this.mbCanvas.getBoundingClientRect();
        const x = Math.floor((e.clientX - rect.left) / this.mbCellSize);
        const y = Math.floor((e.clientY - rect.top) / this.mbCellSize);
        
        if (x < 0 || x > 7 || y < 0 || y > 7) return;
        
        const center = 4;
        const dx = x - center;
        const dy = y - center;
        
        if (dx === 0 && dy === 0) return;
        
        if (isAttack) {
            if (!this.mbAddedAttacks.some(a => a[0] === dx && a[1] === dy)) {
                this.mbAddedAttacks.push([dx, dy]);
            }
        } else {
            if (!this.mbAddedMoves.some(m => m[0] === dx && m[1] === dy)) {
                this.mbAddedMoves.push([dx, dy]);
            }
        }
        
        this.updateMbStats();
        this.drawMoveBoard();
        this.setDevStatus(`Added ${isAttack ? 'attack' : 'move'}: (${dx}, ${dy})`);
    }
    
    drawMoveBoard() {
        const ctx = this.mbCtx;
        const size = this.mbCellSize;
        const center = 4;
        
        ctx.clearRect(0, 0, this.mbCanvas.width, this.mbCanvas.height);
        
        // Доска
        for (let x = 0; x < 8; x++) {
            for (let y = 0; y < 8; y++) {
                ctx.fillStyle = (x + y) % 2 === 0 ? this.colors.boardLight : this.colors.boardDark;
                ctx.fillRect(x * size, y * size, size, size);
            }
        }
        
        // Добавленные ходы (cyan)
        this.mbAddedMoves.forEach(([dx, dy]) => {
            const x = center + dx, y = center + dy;
            if (x >= 0 && x < 8 && y >= 0 && y < 8) {
                ctx.fillStyle = 'rgba(0, 255, 247, 0.4)';
                ctx.fillRect(x * size, y * size, size, size);
                ctx.strokeStyle = '#00fff7';
                ctx.lineWidth = 2;
                ctx.strokeRect(x * size + 1, y * size + 1, size - 2, size - 2);
            }
        });
        
        // Добавленные атаки (magenta)
        this.mbAddedAttacks.forEach(([dx, dy]) => {
            const x = center + dx, y = center + dy;
            if (x >= 0 && x < 8 && y >= 0 && y < 8) {
                ctx.fillStyle = 'rgba(255, 0, 255, 0.4)';
                ctx.fillRect(x * size, y * size, size, size);
                ctx.strokeStyle = '#ff00ff';
                ctx.lineWidth = 2;
                ctx.strokeRect(x * size + 1, y * size + 1, size - 2, size - 2);
            }
        });
        
        // Стандартные ходы фигуры
        const validMoves = this.getStandardMoves(this.mbPieceTypes[this.mbPieceIndex], center, center);
        validMoves.moves.forEach(([mx, my]) => {
            if (!this.mbAddedMoves.some(m => m[0] === mx - center && m[1] === my - center)) {
                ctx.fillStyle = 'rgba(168, 85, 247, 0.5)';
                ctx.beginPath();
                ctx.arc(mx * size + size / 2, my * size + size / 2, size / 4, 0, Math.PI * 2);
                ctx.fill();
            }
        });
        
        // Фигура в центре
        this.drawPieceAt(ctx, { color: this.mbColor, type: this.mbPieceTypes[this.mbPieceIndex] }, center, center, size);
    }
    
    getStandardMoves(type, px, py) {
        const moves = [];
        const addMove = (x, y) => { if (x >= 0 && x < 8 && y >= 0 && y < 8) moves.push([x, y]); };
        
        switch (type) {
            case 'pawn':
                const dir = this.mbColor === 'white' ? -1 : 1;
                addMove(px, py + dir);
                addMove(px, py + 2 * dir);
                break;
            case 'rook':
                for (let i = 1; i < 8; i++) { addMove(px + i, py); addMove(px - i, py); addMove(px, py + i); addMove(px, py - i); }
                break;
            case 'knight':
                [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]].forEach(([dx,dy]) => addMove(px+dx, py+dy));
                break;
            case 'bishop':
                for (let i = 1; i < 8; i++) { addMove(px+i, py+i); addMove(px-i, py-i); addMove(px+i, py-i); addMove(px-i, py+i); }
                break;
            case 'queen':
                for (let i = 1; i < 8; i++) {
                    addMove(px+i, py); addMove(px-i, py); addMove(px, py+i); addMove(px, py-i);
                    addMove(px+i, py+i); addMove(px-i, py-i); addMove(px+i, py-i); addMove(px-i, py+i);
                }
                break;
            case 'king':
                [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]].forEach(([dx,dy]) => addMove(px+dx, py+dy));
                break;
        }
        return { moves: moves.filter(([x,y]) => !(x === px && y === py)) };
    }
    
    drawPieceAt(ctx, piece, x, y, cellSize) {
        const cx = x * cellSize + cellSize / 2;
        const cy = y * cellSize + cellSize / 2;
        const color = piece.color === 'white' ? this.colors.white : this.colors.black;
        const outline = piece.color === 'white' ? this.colors.outline.white : this.colors.outline.black;
        const scale = cellSize / 60;
        
        ctx.save();
        ctx.fillStyle = color;
        ctx.strokeStyle = outline;
        ctx.lineWidth = 2 * scale;
        
        // Glow эффект только для Neon темы
        if (this.colors.pieceGlow && piece.color === 'black') {
            ctx.shadowColor = '#00fff7';
            ctx.shadowBlur = 8 * scale;
        }
        
        switch (piece.type) {
            case 'pawn':
                ctx.beginPath(); ctx.arc(cx, cy, 12*scale, 0, Math.PI*2); ctx.fill(); ctx.stroke();
                ctx.beginPath(); ctx.arc(cx, cy-5*scale, 9*scale, 0, Math.PI*2); ctx.fill(); ctx.stroke();
                ctx.beginPath(); ctx.arc(cx, cy-10*scale, 6*scale, 0, Math.PI*2); ctx.fill(); ctx.stroke();
                break;
            case 'rook':
                ctx.fillRect(cx-12*scale, cy-8*scale, 24*scale, 20*scale);
                ctx.strokeRect(cx-12*scale, cy-8*scale, 24*scale, 20*scale);
                for (let i = 0; i < 3; i++) {
                    ctx.fillRect(cx-10*scale + i*8*scale, cy-14*scale, 6*scale, 6*scale);
                    ctx.strokeRect(cx-10*scale + i*8*scale, cy-14*scale, 6*scale, 6*scale);
                }
                break;
            case 'knight':
                ctx.beginPath();
                ctx.moveTo(cx-10*scale, cy+10*scale); ctx.lineTo(cx+10*scale, cy+10*scale);
                ctx.lineTo(cx+8*scale, cy-5*scale); ctx.lineTo(cx+5*scale, cy-12*scale);
                ctx.lineTo(cx-5*scale, cy-8*scale); ctx.lineTo(cx-10*scale, cy+5*scale);
                ctx.closePath(); ctx.fill(); ctx.stroke();
                break;
            case 'bishop':
                ctx.beginPath();
                ctx.moveTo(cx, cy-15*scale); ctx.lineTo(cx+10*scale, cy+12*scale); ctx.lineTo(cx-10*scale, cy+12*scale);
                ctx.closePath(); ctx.fill(); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(cx-5*scale, cy-12*scale); ctx.lineTo(cx+5*scale, cy-12*scale);
                ctx.moveTo(cx, cy-18*scale); ctx.lineTo(cx, cy-8*scale); ctx.stroke();
                break;
            case 'queen':
                ctx.beginPath();
                for (let i = 0; i < 5; i++) {
                    const angle = (i * 72 - 90) * Math.PI / 180;
                    const px = cx + Math.cos(angle) * 12*scale;
                    const py = cy + Math.sin(angle) * 12*scale;
                    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
                }
                ctx.closePath(); ctx.fill(); ctx.stroke();
                break;
            case 'king':
                ctx.beginPath(); ctx.arc(cx, cy, 10*scale, 0, Math.PI*2); ctx.fill(); ctx.stroke();
                ctx.fillRect(cx-6*scale, cy-8*scale, 12*scale, 14*scale);
                ctx.strokeRect(cx-6*scale, cy-8*scale, 12*scale, 14*scale);
                ctx.shadowBlur = 0;
                ctx.fillStyle = this.colors.crown;
                ctx.beginPath();
                ctx.moveTo(cx-8*scale, cy-8*scale); ctx.lineTo(cx-4*scale, cy-14*scale);
                ctx.lineTo(cx, cy-10*scale); ctx.lineTo(cx+4*scale, cy-14*scale);
                ctx.lineTo(cx+8*scale, cy-8*scale); ctx.closePath(); ctx.fill(); ctx.stroke();
                break;
        }
        ctx.restore();
    }
    
    // ============ ИГРОВАЯ ЛОГИКА ============
    initBoard() {
        this.board = this.getInitialBoard();
        this.draw();
    }
    
    getInitialBoard() {
        const board = Array(8).fill(null).map(() => Array(8).fill(null));
        const pieces = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook'];
        for (let x = 0; x < 8; x++) {
            board[x][0] = { color: 'black', type: pieces[x], moved: false };
            board[x][1] = { color: 'black', type: 'pawn', moved: false };
            board[x][6] = { color: 'white', type: 'pawn', moved: false };
            board[x][7] = { color: 'white', type: pieces[x], moved: false };
        }
        return board;
    }
    
    joinRoom(roomId) {
        this.isLocalGame = false;
        this.roomId = roomId;
        this.moveHistory = [];
        this.updateMoveHistoryDisplay();
        document.getElementById('current-room').textContent = roomId;
        
        this.connectWebSocket();
    }
    
    connectWebSocket() {
        if (this.ws) this.ws.close();
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/${this.roomId}/${this.playerId}`);
        
        this.ws.onopen = () => {
            document.getElementById('status').textContent = 'Подключено. Ожидание противника...';
            this.updateConnectionStatus(true);
            this.reconnectAttempts = 0;
            this.isReconnecting = false;
            this.showScreen('game-screen');
            // Дополнительный вызов для гарантии
            setTimeout(() => this.hideSwitchersPanel(), 10);
        };
        
        this.ws.onmessage = (e) => this.handleServerMessage(JSON.parse(e.data));
        
        this.ws.onclose = () => {
            this.updateConnectionStatus(false);
            if (!this.isReconnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.attemptReconnect();
            } else {
                document.getElementById('status').textContent = 'Отключено';
            }
        };
        
        this.ws.onerror = () => {
            this.updateConnectionStatus(false);
            document.getElementById('status').textContent = 'Ошибка подключения';
        };
    }
    
    attemptReconnect() {
        this.isReconnecting = true;
        this.reconnectAttempts++;
        this.updateConnectionStatus(false);
        
        setTimeout(() => {
            if (this.reconnectAttempts <= this.maxReconnectAttempts) {
                this.connectWebSocket();
            }
        }, this.reconnectDelay);
    }
    
    handleServerMessage(data) {
        switch (data.type) {
            case 'init':
                this.myColor = data.color;
                this.board = data.board;
                this.currentPlayer = data.current_player;
                this.customMoves = data.custom_moves || { white: {}, black: {} };
                this.abilityCards = data.ability_cards || { white: {}, black: {} };
                this.timers = data.timers || { white: 600, black: 600 };
                this.lastMove = null;
                this.startTimer();
                document.getElementById('my-color').textContent = data.color === 'white' ? 'Белые' : data.color === 'black' ? 'Чёрные' : 'Наблюдатель';
                this.updateStatus(data.players_count);
                this.updateCardList();
                this.draw();
                break;
                
            case 'custom_moves_updated':
                this.customMoves = data.custom_moves;
                this.draw();
                break;
                
            case 'cards_updated':
                this.abilityCards = data.ability_cards;
                this.customMoves = data.custom_moves;
                this.updateCardList();
                this.draw();
                this.setDevStatus('Data synced');
                break;
                
            case 'player_joined':
            case 'player_left':
                this.updateStatus(data.players_count);
                if (data.type === 'player_joined') {
                    this.addChatMessage(null, 'Противник подключился', true);
                } else {
                    this.addChatMessage(null, 'Противник отключился', true);
                }
                break;
                
            case 'move':
                const piece = this.board[data.from[0]][data.from[1]];
                const captured = this.board[data.to[0]][data.to[1]];
                
                this.board = data.board;
                this.currentPlayer = data.current_player;
                if (data.timers) this.timers = data.timers;
                this.lastMove = { from: data.from, to: data.to };
                this.selectedPiece = null;
                this.validMoves = [];
                this.validAttacks = [];
                
                if (piece) {
                    this.addMoveToHistory(data.from, data.to, piece, captured);
                }
                
                this.updateTurnIndicator();
                this.draw();
                
                if (data.checkmate) {
                    this.recordResult(data.current_player === 'white' ? 'black' : 'white');
                    this.showGameOver(data.current_player === 'white' ? 'Чёрные' : 'Белые', 'мат');
                } else if (data.stalemate) {
                    this.recordResult('draw');
                    this.showGameOver('Ничья', 'пат');
                } else if (data.check) {
                    document.getElementById('status').textContent = 'ШАХ!';
                }
                break;
                
            case 'valid_moves':
                this.validMoves = data.moves;
                this.validAttacks = data.attacks;
                this.draw();
                break;
                
            case 'game_over':
                if (data.reason === 'resign') {
                    this.recordResult(data.winner);
                    this.showGameOver(data.winner === 'white' ? 'Белые' : 'Чёрные', 'противник сдался');
                } else if (data.reason === 'draw') {
                    this.recordResult('draw');
                    this.showGameOver('Ничья', 'соглашение');
                }
                break;
                
            case 'chat':
                this.addChatMessage('Opponent', data.message);
                break;
                
            case 'draw_offered':
                this.showDrawOffer();
                this.addChatMessage(null, 'Противник предлагает ничью', true);
                break;
                
            case 'draw_declined':
                this.addChatMessage(null, 'Ничья отклонена', true);
                break;
        }
    }
    
    recordResult(result) {
        this.stats.total++;
        if (result === 'white') this.stats.white++;
        else if (result === 'black') this.stats.black++;
        else this.stats.draws++;
        this.saveStats();
    }
    
    updateStatus(count) {
        document.getElementById('status').textContent = count < 2 ? 'Ожидание противника...' : 'Игра началась!';
        this.updateTurnIndicator();
    }
    
    updateTurnIndicator() {
        const indicator = document.getElementById('turn-indicator');
        indicator.textContent = this.currentPlayer === 'white' ? 'Ход белых' : 'Ход чёрных';
        indicator.className = 'turn ' + this.currentPlayer;
        this.updateTimerDisplay();
    }
    
    startTimer() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => {
            if (this.timers[this.currentPlayer] > 0) {
                this.timers[this.currentPlayer]--;
                this.updateTimerDisplay();
                if (this.timers[this.currentPlayer] === 0) {
                    clearInterval(this.timerInterval);
                    const winner = this.currentPlayer === 'white' ? 'Чёрные' : 'Белые';
                    this.showGameOver(winner, 'время вышло');
                }
            }
        }, 1000);
    }
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }
    
    updateTimerDisplay() {
        const formatTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
        
        const whiteEl = document.getElementById('timer-white');
        const blackEl = document.getElementById('timer-black');
        
        if (whiteEl) {
            whiteEl.textContent = formatTime(this.timers.white);
            whiteEl.classList.toggle('low', this.timers.white < 60);
        }
        if (blackEl) {
            blackEl.textContent = formatTime(this.timers.black);
            blackEl.classList.toggle('low', this.timers.black < 60);
        }
        
        document.querySelector('.player-info.self').classList.toggle('active', this.isLocalGame || this.myColor === this.currentPlayer);
        document.querySelector('.player-info.opponent').classList.toggle('active', !this.isLocalGame && this.myColor !== this.currentPlayer);
    }
    
    showGameOver(winner, reason) {
        this.stopTimer();
        document.getElementById('game-over-title').textContent = 'Игра окончена';
        document.getElementById('game-over-message').textContent = reason === 'пат' || reason === 'соглашение' ? `${winner}!` : `Победа: ${winner} (${reason})`;
        document.getElementById('game-over-modal').classList.remove('hidden');
    }
    
    handleTouch(event) {
        event.preventDefault();
        const touch = event.touches[0];
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.floor((touch.clientX - rect.left) / this.cellSize);
        const y = Math.floor((touch.clientY - rect.top) / this.cellSize);
        
        if (x < 0 || x > 7 || y < 0 || y > 7) return;
        
        if (this.isLocalGame) this.handleLocalClick(x, y);
        else this.handleOnlineClick(x, y);
    }
    
    handleClick(event, isRightClick = false) {
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.floor((event.clientX - rect.left) / this.cellSize);
        const y = Math.floor((event.clientY - rect.top) / this.cellSize);
        
        if (x < 0 || x > 7 || y < 0 || y > 7) return;
        
        if (this.isLocalGame) this.handleLocalClick(x, y);
        else this.handleOnlineClick(x, y);
    }
    
    handleLocalClick(x, y) {
        const clickedPiece = this.board[x][y];
        
        if (this.selectedPiece) {
            const [sx, sy] = this.selectedPiece;
            const isValidMove = this.validMoves.some(m => m[0] === x && m[1] === y);
            const isValidAttack = this.validAttacks.some(a => a[0] === x && a[1] === y);
            
            if (isValidMove || isValidAttack) {
                const piece = this.board[sx][sy];
                const captured = this.board[x][y];
                
                this.board[sx][sy] = null;
                this.board[x][y] = piece;
                piece.moved = true;
                if (piece.type === 'pawn' && (y === 0 || y === 7)) piece.type = 'queen';
                
                this.lastMove = { from: [sx, sy], to: [x, y] };
                this.addMoveToHistory([sx, sy], [x, y], piece, captured);
                
                this.selectedPiece = null;
                this.validMoves = [];
                this.validAttacks = [];
                this.currentPlayer = this.currentPlayer === 'white' ? 'black' : 'white';
                this.updateTurnIndicator();
                this.draw();
                return;
            }
        }
        
        if (clickedPiece && clickedPiece.color === this.currentPlayer) {
            this.selectedPiece = [x, y];
            this.calculateValidMoves(x, y);
            document.getElementById('selected-piece-info').textContent = `${clickedPiece.color === 'white' ? 'Белая' : 'Чёрная'} ${this.getPieceNameRu(clickedPiece.type)}`;
        } else {
            this.deselectPiece();
        }
        this.draw();
    }
    
    
    calculateValidMoves(x, y) {
        const piece = this.board[x][y];
        if (!piece) return;
        
        this.validMoves = [];
        this.validAttacks = [];
        
        const addMove = (nx, ny) => {
            if (nx < 0 || nx > 7 || ny < 0 || ny > 7) return false;
            const target = this.board[nx][ny];
            if (!target) { this.validMoves.push([nx, ny]); return true; }
            else if (target.color !== piece.color) this.validAttacks.push([nx, ny]);
            return false;
        };
        
        const addAttack = (nx, ny) => {
            if (nx < 0 || nx > 7 || ny < 0 || ny > 7) return;
            const target = this.board[nx][ny];
            if (target && target.color !== piece.color) this.validAttacks.push([nx, ny]);
        };
        
        switch (piece.type) {
            case 'pawn':
                const dir = piece.color === 'white' ? -1 : 1;
                if (!this.board[x][y + dir]) {
                    this.validMoves.push([x, y + dir]);
                    if (!piece.moved && !this.board[x][y + 2 * dir]) this.validMoves.push([x, y + 2 * dir]);
                }
                [-1, 1].forEach(dx => addAttack(x + dx, y + dir));
                break;
            case 'rook':
                [[0,1],[0,-1],[1,0],[-1,0]].forEach(([dx,dy]) => { for (let i = 1; i < 8; i++) if (!addMove(x+dx*i, y+dy*i)) break; });
                break;
            case 'knight':
                [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]].forEach(([dx,dy]) => addMove(x+dx, y+dy));
                break;
            case 'bishop':
                [[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([dx,dy]) => { for (let i = 1; i < 8; i++) if (!addMove(x+dx*i, y+dy*i)) break; });
                break;
            case 'queen':
                [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([dx,dy]) => { for (let i = 1; i < 8; i++) if (!addMove(x+dx*i, y+dy*i)) break; });
                break;
            case 'king':
                [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([dx,dy]) => addMove(x+dx, y+dy));
                break;
        }
        
        // Добавляем кастомные ходы
        const custom = this.customMoves[piece.color]?.[piece.type];
        if (custom) {
            custom.moves?.forEach(([dx, dy]) => {
                const nx = x + dx, ny = y + dy;
                if (nx >= 0 && nx < 8 && ny >= 0 && ny < 8 && !this.board[nx][ny]) {
                    if (!this.validMoves.some(m => m[0] === nx && m[1] === ny)) this.validMoves.push([nx, ny]);
                }
            });
            custom.attacks?.forEach(([dx, dy]) => {
                const nx = x + dx, ny = y + dy;
                if (nx >= 0 && nx < 8 && ny >= 0 && ny < 8) {
                    const target = this.board[nx][ny];
                    if (target && target.color !== piece.color && !this.validAttacks.some(a => a[0] === nx && a[1] === ny)) {
                        this.validAttacks.push([nx, ny]);
                    }
                }
            });
        }
    }
    
    handleOnlineClick(x, y) {
        if (this.myColor !== this.currentPlayer) return;
        const clickedPiece = this.board[x][y];
        
        if (this.selectedPiece) {
            const isValid = this.validMoves.some(m => m[0] === x && m[1] === y) || this.validAttacks.some(a => a[0] === x && a[1] === y);
            if (isValid) {
                this.ws.send(JSON.stringify({ type: 'move', from: this.selectedPiece, to: [x, y] }));
                return;
            }
        }
        
        if (clickedPiece && clickedPiece.color === this.myColor) {
            this.selectedPiece = [x, y];
            this.ws.send(JSON.stringify({ type: 'get_valid_moves', position: [x, y] }));
            document.getElementById('selected-piece-info').textContent = `${clickedPiece.color === 'white' ? 'Белая' : 'Чёрная'} ${this.getPieceNameRu(clickedPiece.type)}`;
        } else {
            this.deselectPiece();
            this.draw();
        }
    }
    
    // ============ ОТРИСОВКА ============
    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Доска
        for (let x = 0; x < 8; x++) {
            for (let y = 0; y < 8; y++) {
                this.ctx.fillStyle = (x + y) % 2 === 0 ? this.colors.boardLight : this.colors.boardDark;
                this.ctx.fillRect(x * this.cellSize, y * this.cellSize, this.cellSize, this.cellSize);
            }
        }
        
        // Подсветка последнего хода
        if (this.lastMove) {
            this.ctx.fillStyle = this.colors.lastMove;
            this.ctx.fillRect(this.lastMove.from[0] * this.cellSize, this.lastMove.from[1] * this.cellSize, this.cellSize, this.cellSize);
            this.ctx.fillRect(this.lastMove.to[0] * this.cellSize, this.lastMove.to[1] * this.cellSize, this.cellSize, this.cellSize);
        }
        
        // Выделенная клетка
        if (this.selectedPiece) {
            const [sx, sy] = this.selectedPiece;
            this.ctx.fillStyle = this.colors.selected;
            this.ctx.fillRect(sx * this.cellSize, sy * this.cellSize, this.cellSize, this.cellSize);
        }
        
        // Возможные ходы
        this.validMoves.forEach(([mx, my]) => {
            this.ctx.fillStyle = this.colors.highlightMove;
            this.ctx.beginPath();
            this.ctx.arc(mx * this.cellSize + this.cellSize / 2, my * this.cellSize + this.cellSize / 2, 10, 0, Math.PI * 2);
            this.ctx.fill();
        });
        
        // Возможные атаки
        this.validAttacks.forEach(([ax, ay]) => {
            this.ctx.fillStyle = this.colors.highlightAttack;
            this.ctx.beginPath();
            this.ctx.arc(ax * this.cellSize + this.cellSize / 2, ay * this.cellSize + this.cellSize / 2, 10, 0, Math.PI * 2);
            this.ctx.fill();
        });
        
        // Фигуры
        for (let x = 0; x < 8; x++) {
            for (let y = 0; y < 8; y++) {
                const piece = this.board[x][y];
                if (piece) this.drawPiece(piece, x, y);
            }
        }
    }
    
    drawPiece(piece, x, y) {
        this.drawPieceAt(this.ctx, piece, x, y, this.cellSize);
    }
    
    // Обновление цветов при смене темы
    updateThemeColors(theme) {
        this.colors = this.themes[theme] || this.themes.neon;
        this.draw();
        if (this.moveBoardOpen) {
            this.drawMoveBoard();
        }
    }
}

// ============ ПЕРЕКЛЮЧАТЕЛЬ ТЕМ ============
class ThemeSwitcher {
    constructor() {
        this.currentTheme = localStorage.getItem('chess_theme_v2') || 'neon';
        this.applyTheme(this.currentTheme);
        this.initButtons();
    }
    
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.currentTheme = theme;
        localStorage.setItem('chess_theme_v2', theme);
        this.updateButtons();
        
        // Обновляем цвета в игре если она существует
        if (window.game) {
            window.game.updateThemeColors(theme);
        }
    }
    
    updateButtons() {
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === this.currentTheme);
        });
    }
    
    initButtons() {
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => this.applyTheme(btn.dataset.theme));
        });
        this.updateButtons();
    }
}

// Проверка параметра room в URL
const urlParams = new URLSearchParams(window.location.search);
const roomParam = urlParams.get('room');

const themeSwitcher = new ThemeSwitcher();
const game = new ChessGame();
window.game = game;

// Наблюдатель за изменениями видимости game-screen
const gameScreenObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
            const gameScreen = document.getElementById('game-screen');
            if (gameScreen) {
                if (gameScreen.classList.contains('hidden')) {
                    if (game && game.showSwitchersPanel) {
                        game.showSwitchersPanel();
                    }
                } else {
                    if (game && game.hideSwitchersPanel) {
                        game.hideSwitchersPanel();
                    }
                }
            }
        }
    });
});

// Инициализация наблюдателя
const initSwitcherObserver = () => {
    const gameScreen = document.getElementById('game-screen');
    if (gameScreen) {
        gameScreenObserver.observe(gameScreen, {
            attributes: true,
            attributeFilter: ['class']
        });
        
        // Проверяем начальное состояние
        if (!gameScreen.classList.contains('hidden')) {
            if (game && game.hideSwitchersPanel) {
                game.hideSwitchersPanel();
            }
        }
    }
};

// Инициализируем после загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSwitcherObserver);
} else {
    initSwitcherObserver();
}

// Дополнительная проверка каждые 100мс для гарантии
setInterval(() => {
    const gameScreen = document.getElementById('game-screen');
    const switchersPanel = document.querySelector('.switchers-panel');
    if (gameScreen && switchersPanel) {
        if (!gameScreen.classList.contains('hidden')) {
            // Игра активна - скрываем переключатель
            if (!switchersPanel.classList.contains('hidden-in-game')) {
                if (game && game.hideSwitchersPanel) {
                    game.hideSwitchersPanel();
                } else {
                    // Fallback если функция недоступна
                    document.body.classList.add('game-active');
                    switchersPanel.classList.add('hidden-in-game');
                    switchersPanel.style.display = 'none';
                    switchersPanel.style.visibility = 'hidden';
                    switchersPanel.style.opacity = '0';
                    switchersPanel.style.pointerEvents = 'none';
                    switchersPanel.style.zIndex = '-1';
                }
            }
        } else {
            // Игра не активна - показываем переключатель
            if (switchersPanel.classList.contains('hidden-in-game')) {
                if (game && game.showSwitchersPanel) {
                    game.showSwitchersPanel();
                } else {
                    // Fallback если функция недоступна
                    document.body.classList.remove('game-active');
                    switchersPanel.classList.remove('hidden-in-game');
                    switchersPanel.style.display = '';
                    switchersPanel.style.visibility = '';
                    switchersPanel.style.opacity = '';
                    switchersPanel.style.pointerEvents = '';
                    switchersPanel.style.zIndex = '';
                }
            }
        }
    }
}, 100);

if (roomParam) {
    game.joinRoom(roomParam);
}

