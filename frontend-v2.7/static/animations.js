// animations.js - Класс для управления анимациями фигур
class PieceAnimation {
    constructor(ctx, cellSize, coordsOffset) {
        this.ctx = ctx;
        this.cellSize = cellSize;
        this.coordsOffset = coordsOffset;
        this.activeAnimations = [];
    }
    
    animateMove(from, to, piece, duration = 300, onComplete = null) {
        const [fx, fy] = from;
        const [tx, ty] = to;
        const startX = fx * this.cellSize + this.coordsOffset;
        const startY = fy * this.cellSize + this.coordsOffset;
        const endX = tx * this.cellSize + this.coordsOffset;
        const endY = ty * this.cellSize + this.coordsOffset;
        
        const animation = {
            piece: piece,
            startX, startY,
            endX, endY,
            startTime: Date.now(),
            duration: duration,
            onComplete: onComplete
        };
        
        this.activeAnimations.push(animation);
        return animation;
    }
    
    update() {
        const now = Date.now();
        this.activeAnimations = this.activeAnimations.filter(anim => {
            const elapsed = now - anim.startTime;
            const progress = Math.min(elapsed / anim.duration, 1);
            const easeProgress = this.easeInOutCubic(progress);
            
            const currentX = anim.startX + (anim.endX - anim.startX) * easeProgress;
            const currentY = anim.startY + (anim.endY - anim.startY) * easeProgress;
            
            if (progress < 1) {
                anim.currentX = currentX;
                anim.currentY = currentY;
                return true;
            } else {
                if (anim.onComplete) anim.onComplete();
                return false;
            }
        });
    }
    
    easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }
    
    drawAnimatedPiece(piece, x, y) {
        const offsetX = (x - this.coordsOffset) / this.cellSize;
        const offsetY = (y - this.coordsOffset) / this.cellSize;
        // Используем drawPieceAt из ChessGame
        if (window.game && window.game.drawPieceAt) {
            window.game.drawPieceAt(this.ctx, piece, offsetX, offsetY, this.cellSize);
        }
    }
    
    hasActiveAnimations() {
        return this.activeAnimations.length > 0;
    }
}

