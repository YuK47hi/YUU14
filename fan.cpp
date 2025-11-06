#include "fan.h" 
#include <cmath>

// DrawFan 関数の定義 (isTiltedUp 引数と関連ロジックを削除)
void DrawFan(int x, int y, FanSpeed speed) {
    int bodyColor = GetColor(150, 150, 150);
    int bladeColor = GetColor(100, 100, 200);

    // 台座と支柱の描画
    DrawBox(x + 50, y + 250, x + 150, y + 280, bodyColor, TRUE);
    DrawBox(x + 90, y + 110, x + 110, y + 250, bodyColor, TRUE);

    int motorBaseX = x + 100;
    int motorBaseY = y + 100;

    // 首振りのオフセット計算ロジックを削除したため、固定の位置で描画
    int fixedHeadX = motorBaseX;
    int fixedHeadY = motorBaseY;

    // モーターヘッドとガードの描画
    DrawCircle(fixedHeadX, fixedHeadY, 40, bodyColor, TRUE);
    DrawCircle(fixedHeadX, fixedHeadY, 70, bodyColor, FALSE);

    // 羽根の描画（風速ONの場合のみ回転）
    if (speed != FanSpeed::OFF) {
        double angleSpeed = 0.0;
        if (speed == FanSpeed::LOW) angleSpeed = 0.01;
        else if (speed == FanSpeed::MEDIUM) angleSpeed = 0.03;
        else if (speed == FanSpeed::HIGH) angleSpeed = 0.05;

        double angleOffset = GetNowCount() * angleSpeed;

        for (int i = 0; i < 3; ++i) {
            double angle = (2.0 * DX_PI_F / 3.0) * i + angleOffset;
            int bladeX1 = fixedHeadX + static_cast<int>(std::cos(angle - 0.1) * 60);
            int bladeY1 = fixedHeadY + static_cast<int>(std::sin(angle - 0.1) * 60);
            int bladeX2 = fixedHeadX + static_cast<int>(std::cos(angle + 0.1) * 60);
            int bladeY2 = fixedHeadY + static_cast<int>(std::sin(angle + 0.1) * 60);
            int bladeX3 = fixedHeadX + static_cast<int>(std::cos(angle) * 70);
            int bladeY3 = fixedHeadY + static_cast<int>(std::sin(angle) * 70);

            DrawTriangle(bladeX1, bladeY1, bladeX2, bladeY2, bladeX3, bladeY3, bladeColor, TRUE);
        }
    }
}