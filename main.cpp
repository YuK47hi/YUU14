#define DX_LIB_OVERRIDE_WINMAIN

#include "Dxlib.h"
#include "fan.h" 
#include <iostream>
#include <vector>
#include <string>

// ボタンの情報を管理する構造
struct Button {
    int x;
    int y;
    int width;
    int height;
    std::string text;
    std::string type;
    FanSpeed speed;
    Difficulty difficulty;
};

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {

    SetOutApplicationLogValidFlag(FALSE);
    ChangeWindowMode(TRUE);
    SetMainWindowText("扇風機ゲーム");
    if (DxLib_Init() == -1) {
        return -1;
    }
    SetDrawScreen(DX_SCREEN_BACK);

    GameState currentGameState = GameState::TITLE_SCREEN;
    FanSpeed currentSpeed = FanSpeed::OFF;
    double power = 100.0;
    double powerConsumptionLow, powerConsumptionMedium, powerConsumptionHigh;
    double powerRechargeRate;
    int gameStartTime = 0;
    int clearTime = 0; // 今回は「制限時間」として使用

    int windowWidth, windowHeight;
    GetWindowSize(&windowWidth, &windowHeight);

    // --- 難易度ボタン計算 ---
    int difficultyButtonWidth = 150;
    int difficultyButtonMargin = 50;
    int totalDifficultyButtonsWidth = (difficultyButtonWidth * 3) + (difficultyButtonMargin * 2);
    int difficultyStartX = (windowWidth - totalDifficultyButtonsWidth) / 2;

    // --- 速度ボタン計算 ---
    int speedButtonWidth = 80;
    int speedButtonHeight = 40;
    int speedButtonMargin = 30;
    int totalSpeedButtonsWidth = (speedButtonWidth * 4) + (speedButtonMargin * 3);
    int speedStartX = (windowWidth - totalSpeedButtonsWidth) / 2;

    std::vector<Button> buttons = {
        // ゲーム中のボタン
        {speedStartX, 400, speedButtonWidth, speedButtonHeight, "弱", "speed", FanSpeed::LOW, Difficulty::EASY},
        {speedStartX + speedButtonWidth + speedButtonMargin, 400, speedButtonWidth, speedButtonHeight, "中", "speed", FanSpeed::MEDIUM, Difficulty::EASY},
        {speedStartX + (speedButtonWidth + speedButtonMargin) * 2, 400, speedButtonWidth, speedButtonHeight, "強", "speed", FanSpeed::HIGH, Difficulty::EASY},
        {speedStartX + (speedButtonWidth + speedButtonMargin) * 3, 400, speedButtonWidth, speedButtonHeight, "切る", "speed", FanSpeed::OFF, Difficulty::EASY},

        // タイトル画面の難易度選択ボタン
        {difficultyStartX, 250, difficultyButtonWidth, 50, "かんたん", "difficulty", FanSpeed::OFF, Difficulty::EASY},
        {difficultyStartX + difficultyButtonWidth + difficultyButtonMargin, 250, difficultyButtonWidth, 50, "ふつう", "difficulty", FanSpeed::OFF, Difficulty::NORMAL},
        {difficultyStartX + (difficultyButtonWidth + difficultyButtonMargin) * 2, 250, difficultyButtonWidth, 50, "むずかしい", "difficulty", FanSpeed::OFF, Difficulty::HARD}
    };

    // --- 扇風機とHPバーの中央配置の計算 ---

    const int FAN_DRAW_WIDTH = 200;
    const int FAN_CENTER_X = (windowWidth - FAN_DRAW_WIDTH) / 2;
    const int FAN_POS_Y = 100;

    const int HP_BAR_WIDTH = 200;
    const int HP_BAR_START_X = (windowWidth - HP_BAR_WIDTH) / 2;
    const int HP_BAR_POS_Y = 30;

    const int UI_TEXT_START_X = HP_BAR_START_X;

    // --- 中央配置の計算ここまで ---

    while (ProcessMessage() == 0 && CheckHitKey(KEY_INPUT_ESCAPE) == 0) {
        int mouseX, mouseY;
        GetMousePoint(&mouseX, &mouseY);
        int mouseInput = GetMouseInput();
        ClearDrawScreen();

        switch (currentGameState) {
        case GameState::TITLE_SCREEN: {
            const char* titleText = "省エネ扇風機チャレンジ";
            int titleTextWidth = GetDrawFormatStringWidth(titleText);
            DrawFormatString((windowWidth - titleTextWidth) / 2, 150, GetColor(255, 255, 255), "%s", titleText);
            const char* subtitleText = "難易度を選んでください";
            int subtitleTextWidth = GetDrawFormatStringWidth(subtitleText);
            DrawFormatString((windowWidth - subtitleTextWidth) / 2, 200, GetColor(255, 255, 255), "%s", subtitleText);

            // ルールの説明
            DrawFormatString((windowWidth - GetDrawFormatStringWidth("ルール: 制限時間内に電力を40%%以下(60%%以上消費)にしてください。")) / 2, 350, GetColor(255, 255, 0), "ルール: 制限時間内に電力を40%%以下(60%%以上消費)にしてください。");

            for (const auto& button : buttons) {
                if (button.type == "difficulty") {
                    DrawBox(button.x, button.y, button.x + button.width, button.y + button.height, GetColor(0, 100, 200), TRUE);
                    DrawString(button.x + 20, button.y + 15, button.text.c_str(), GetColor(255, 255, 255));
                    if (mouseInput & MOUSE_INPUT_LEFT) {
                        if (mouseX > button.x && mouseX < button.x + button.width && mouseY > button.y && mouseY < button.y + button.height) {
                            currentGameState = GameState::IN_GAME;
                            power = 100.0;
                            gameStartTime = GetNowCount();

                            // 難易度ごとの設定
                            switch (button.difficulty) {
                            case Difficulty::EASY:
                                powerConsumptionLow = 0.005;
                                powerConsumptionMedium = 0.015;
                                powerConsumptionHigh = 0.035;
                                powerRechargeRate = 0.001;
                                clearTime = 60000; // 制限時間 60秒
                                break;
                            case Difficulty::NORMAL:
                                powerConsumptionLow = 0.003;
                                powerConsumptionMedium = 0.01;
                                powerConsumptionHigh = 0.025;
                                powerRechargeRate = 0.002;
                                clearTime = 45000; // 制限時間 45秒
                                break;
                            case Difficulty::HARD:
                                powerConsumptionLow = 0.002;
                                powerConsumptionMedium = 0.008;
                                powerConsumptionHigh = 0.02;
                                powerRechargeRate = 0.003;
                                clearTime = 30000; // 制限時間 30秒
                                break;
                            }
                        }
                    }
                }
            }
            break;
        }
        case GameState::IN_GAME: {

            // --- UIの描画 (中央寄せ) ---
            int elapsedTime = GetNowCount() - gameStartTime;
            int remainingTime = clearTime - elapsedTime;

            // 1. 電力(HP)バーの描画 (中央)
            DrawBox(HP_BAR_START_X, HP_BAR_POS_Y, HP_BAR_START_X + HP_BAR_WIDTH, HP_BAR_POS_Y + 20, GetColor(200, 200, 200), FALSE);
            DrawBox(HP_BAR_START_X, HP_BAR_POS_Y, HP_BAR_START_X + static_cast<int>(power * 2), HP_BAR_POS_Y + 20, GetColor(0, 255, 0), TRUE);

            // 2. 電力、タイマー、情報の描画
            DrawFormatString(HP_BAR_START_X, HP_BAR_POS_Y + 25, GetColor(255, 255, 255), "電力: %.1f", power);

            // タイマーは画面右上に配置
            DrawFormatString(windowWidth - 150, HP_BAR_POS_Y, GetColor(255, 255, 255), "残り時間: %.1f秒", (double)remainingTime / 1000.0);

            // 風速のテキスト表示（HPバーの下に揃えて中央寄せ）
            DrawFormatString(UI_TEXT_START_X, HP_BAR_POS_Y + 50, GetColor(255, 255, 255), "現在の風速: ");
            int currentSpeedTextX = UI_TEXT_START_X + GetDrawFormatStringWidth("現在の風速: ");

            switch (currentSpeed) {
            case FanSpeed::OFF:
                DrawString(currentSpeedTextX, HP_BAR_POS_Y + 50, "切", GetColor(255, 255, 255));
                break;
            case FanSpeed::LOW:
                DrawString(currentSpeedTextX, HP_BAR_POS_Y + 50, "弱", GetColor(255, 255, 255));
                break;
            case FanSpeed::MEDIUM:
                DrawString(currentSpeedTextX, HP_BAR_POS_Y + 50, "中", GetColor(255, 255, 255));
                break;
            case FanSpeed::HIGH:
                DrawString(currentSpeedTextX, HP_BAR_POS_Y + 50, "強", GetColor(255, 255, 255));
                break;
            }
            // --- UIの描画ここまで ---

            // --- ゲームクリア・オーバーの判定 ---
            if (power <= 40.0) {
                currentGameState = GameState::GAME_CLEAR;
            }

            if (remainingTime <= 0) {
                currentGameState = GameState::GAME_OVER;
            }

            // ------------------------------------

            if (mouseInput & MOUSE_INPUT_LEFT) {
                for (const auto& button : buttons) {
                    if (button.type == "speed") {
                        if (mouseX > button.x && mouseX < button.x + button.width && mouseY > button.y && mouseY < button.y + button.height) {
                            currentSpeed = button.speed;
                            break;
                        }
                    }
                }
            }

            // 電力消費・回復の計算
            switch (currentSpeed) {
            case FanSpeed::LOW:
                power -= powerConsumptionLow;
                break;
            case FanSpeed::MEDIUM:
                power -= powerConsumptionMedium;
                break;
            case FanSpeed::HIGH:
                power -= powerConsumptionHigh;
                break;
            case FanSpeed::OFF:
                power += powerRechargeRate;
                if (power > 100.0) power = 100.0;
                break;
            }
            if (power < 0.0) {
                power = 0.0;
            }

            DrawFan(FAN_CENTER_X, FAN_POS_Y, currentSpeed);

            for (const auto& button : buttons) {
                if (button.type == "speed") {
                    DrawBox(button.x, button.y, button.x + button.width, button.y + button.height, GetColor(0, 100, 200), TRUE);
                    DrawString(button.x + 15, button.y + 12, button.text.c_str(), GetColor(255, 255, 255));
                }
            }
            break;
        }
        case GameState::GAME_OVER: {
            const char* message = "ゲームオーバー: 制限時間内に目標を達成できませんでした。";
            const char* exit_message = "ESCキーを押して終了";

            // テキストの幅を取得して中央のX座標を計算
            int message_width = GetDrawFormatStringWidth(message);
            int exit_width = GetDrawFormatStringWidth(exit_message);
            int center_x_message = (windowWidth - message_width) / 2;
            int center_x_exit = (windowWidth - exit_width) / 2;

            DrawFormatString(center_x_message, 250, GetColor(255, 0, 0), "%s", message);
            DrawFormatString(center_x_exit, 300, GetColor(255, 255, 255), "%s", exit_message);
            break;
        }
        case GameState::GAME_CLEAR: {
            const char* message = "ゲームクリア！目標電力消費量を達成しました。";
            const char* exit_message = "ESCキーを押して終了";

            // テキストの幅を取得して中央のX座標を計算
            int message_width = GetDrawFormatStringWidth(message);
            int exit_width = GetDrawFormatStringWidth(exit_message);
            int center_x_message = (windowWidth - message_width) / 2;
            int center_x_exit = (windowWidth - exit_width) / 2;

            DrawFormatString(center_x_message, 250, GetColor(0, 255, 0), "%s", message);
            DrawFormatString(center_x_exit, 300, GetColor(255, 255, 255), "%s", exit_message);
            break;
        }
        }
        ScreenFlip();
    }
    DxLib_End();
    return 0;
}