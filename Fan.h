#ifndef FAN_H
#define FAN_H

#include "Dxlib.h"

// 扇風機の風速を表す列挙型
enum class FanSpeed {
    OFF,
    LOW,
    MEDIUM,
    HIGH
};

// 難易度を表す列挙型
enum class Difficulty {
    EASY,
    NORMAL,
    HARD
};

// ゲームの状態を表す列挙型
enum class GameState {
    TITLE_SCREEN,
    IN_GAME,
    GAME_OVER,
    GAME_CLEAR
};

// 扇風機をコードで描画する関数の宣言 (isTiltedUp を削除)
void DrawFan(int x, int y, FanSpeed speed);

#endif // FAN_H