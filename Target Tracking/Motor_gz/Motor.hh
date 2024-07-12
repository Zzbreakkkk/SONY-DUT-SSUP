/*
 * @Author        陈佳辉 1946847867@qq.com
 * @Date          2024-03-12 20:08:51
 * @LastEditTime  2024-03-13 14:36:53
 * @Description   电机驱动
 *
 */
#include "PCA9685.h"
#define Speed_dj 2500
extern PCA9685 pwmController;
/*须在.ino文件中初始化
 * 例：
 * PCA9685 pwmController(B000111);
 *
 * void setup()
 * {
 *     ···
 *     pwmController.resetDevices();
 *     pwmController.init();
 *     pwmController.setPWMFrequency(500);
 *     ···
 * }
 *
 */

/**
 * @brief 电机前进/后退状态位
 */
enum MotorStatus
{
    FORWARD = 4095,
    BACKWARD = 0
};

class Motor
{
private:
    int LBchannel;   // 左后轮pwm通道
    int LBdirection; // 左后轮方向通道
    int RBchannel;   // 右后轮pwm通道
    int RBdirection; // 右后轮方向通道
    int LFchannel;   // 左前轮pwm通道
    int LFdirection; // 左前轮方向通道
    int RFchannel;   // 右前轮pwm通道
    int RFdirection; // 右前轮方向通道

public:
    /**
     * @brief (1, 0, 3, 2, 5, 4, 7, 6)
     * @param {int} a 左后轮pwm通道
     * @param {int} b 左后轮方向通道
     * @param {int} c 右后轮pwm通道
     * @param {int} d 右后轮方向通道
     * @param {int} e 左前轮pwm通道
     * @param {int} f 左前轮方向通道
     * @param {int} g 右前轮pwm通道
     * @param {int} h 右前轮方向通道
     * @return {*}
     */
    Motor(int a, int b, int c, int d, int e, int f, int g, int h)
        : LBchannel(a), LBdirection(b), RBchannel(c), RBdirection(d),
          LFchannel(e), LFdirection(f), RFchannel(g), RFdirection(h){};

    /**
     * @brief 析构
     * @return {*}
     */
    ~Motor();

    /**
     * @brief 电机停转
     * @return {*}
     */
    void MotorOff();

    /**
     * @brief 单轮前转
     * @param {int} channel 轮子pwm通道
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorOneFor(int channel, int speed);

    /**
     * @brief 单轮后转
     * @param {int} channel 轮子pwm通道
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorOneBack(int channel, int speed);

    /**
     * @brief 车前进
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorForward(int speed);

    /**
     * @brief 车后退
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorBackward(int speed);

    /**
     * @brief 车右转（精准转向待优化，校准两轮差速）
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorTurnRight(int speed);

    /**
     * @brief 车左转（精准转向待优化，校准两轮差速）
     * @param {int} speed 速度（0~4095）
     * @return {*}
     */
    void MotorTurnLeft(int speed);

    /**
     * @brief 车转向（角度版）
     * @param {int} flag 0，左；1，右
     * @param {int} angle 转向角度
     * @return {*}
     */
    void MotorTurn(int flag, int angle);
};

Motor::~Motor()
{
}

void Motor::MotorOff()
{
    pwmController.setChannelOff(LBchannel);
    pwmController.setChannelOff(RBchannel);
    pwmController.setChannelOff(LFchannel);
    pwmController.setChannelOff(RFchannel);
}

void Motor::MotorOneFor(int channel, int speed)
{
    pwmController.setChannelPWM(channel - 1, FORWARD);
    pwmController.setChannelPWM(channel, speed);
}

void Motor::MotorOneBack(int channel, int speed)
{
    pwmController.setChannelPWM(channel - 1, BACKWARD);
    pwmController.setChannelPWM(channel, speed);
}

void Motor::MotorForward(int speed)
{
    MotorOneFor(LBchannel, speed);
    MotorOneFor(RBchannel, speed);
    MotorOneFor(LFchannel, speed);
    MotorOneFor(RFchannel, speed);
}

void Motor::MotorBackward(int speed)
{
    MotorOneBack(LBchannel, speed);
    MotorOneBack(RBchannel, speed);
    MotorOneBack(LFchannel, speed);
    MotorOneBack(RFchannel, speed);
}

void Motor::MotorTurnRight(int speed)
{
    MotorOneFor(LBchannel, speed);
    MotorOneFor(RBchannel, speed / 4);
    MotorOneFor(LFchannel, speed);
    MotorOneFor(RFchannel, speed / 4);
}
void Motor::MotorTurnLeft(int speed)
{
    MotorOneFor(LBchannel, speed / 4);
    MotorOneFor(RBchannel, speed);
    MotorOneFor(LFchannel, speed / 4);
    MotorOneFor(RFchannel, speed);
}

#define TIME_DELAY_FACTOR 500 / 3 * 1.5

void Motor::MotorTurn(int flag, int angle)
{
    if (flag == 0)
    {
        MotorOneBack(LBchannel, Speed_dj);
        MotorOneFor(RBchannel, Speed_dj);
        MotorOneBack(RFchannel, Speed_dj);
        MotorOneFor(LFchannel, Speed_dj);
        delay(TIME_DELAY_FACTOR * angle / 90);
        MotorOff();
    }
    else if (flag == 1)
    {
        MotorOneFor(LBchannel, Speed_dj);
        MotorOneBack(RBchannel, Speed_dj);
        MotorOneFor(RFchannel, Speed_dj);
        MotorOneBack(LFchannel, Speed_dj);
        delay(TIME_DELAY_FACTOR * angle / 90);
        MotorOff();
    }
}