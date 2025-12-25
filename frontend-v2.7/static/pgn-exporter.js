// pgn-exporter.js - Класс для экспорта PGN
class PGNExporter {
    static exportGame(moveHistory, whitePlayer = 'White', blackPlayer = 'Black', result = '*') {
        const date = new Date().toISOString().split('T')[0].replace(/-/g, '.');
        let pgn = `[Event "Online Game"]\n`;
        pgn += `[Site "Chess Online"]\n`;
        pgn += `[Date "${date}"]\n`;
        pgn += `[White "${whitePlayer}"]\n`;
        pgn += `[Black "${blackPlayer}"]\n`;
        pgn += `[Result "${result}"]\n\n`;
        
        moveHistory.forEach(move => {
            pgn += `${move.number}. ${move.white || '...'} ${move.black || ''} `;
        });
        
        pgn += result;
        return pgn;
    }
}

