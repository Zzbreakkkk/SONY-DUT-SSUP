/*
 * @Author        陈佳辉 1946847867@qq.com
 * @Date          2024-03-12 15:30:16
 * @LastEditTime  2024-03-13 14:41:10mySerial
 * @Description   电机demo
 *
 */
#include "PCA9685.h"
#include "Motor.hh"
#include <Wire.h>
#define DEPTH_CAMERA_ADDRESS 0x10


#define SELECT 4
#define LEFT 1
#define RIGHT 2
#define UP 0
#define DOWN 3
#define NONE 5
#include <SoftwareSerial.h>

#define RX_PIN 3
#define TX_PIN 4

SoftwareSerial mySerial(RX_PIN, TX_PIN);

PCA9685 pwmController(B000111);
Motor motorCtrl(1, 0, 3, 2, 5, 4, 7, 6);


int dist; //actual distance measurements of LiDAR 
int strength; //signal strength of LiDAR
float temprature;
int check;  //save check value
int sum=0;
int n = 10;
int i;
int mean;
int count = 0;
int dist_array[10];
double left_count = 0.0;
double right_count = 0.0;
unsigned long startTime;
unsigned long elapsedTime;
unsigned long elapsedTime_right;
int n1 = 0;
int ano_left=1;

unsigned long backTime;

void setup()
{
    Serial.begin(115200);
    mySerial.begin(115200);
    Serial2.begin(115200,SERIAL_8N1);
    Wire.begin();

    pwmController.resetDevices();
    pwmController.init();
    pwmController.setPWMFrequency(500);
}
int flag = 0;
void loop()
{   
  if(flag==0){
      backTime = millis();
      while(millis()-backTime<13000){
        dist_back();
    }
    flag = 1;
  }
    
        

    int btnValue = read_data();
    //mySerial.println(btnValue);
    n1++;
    if (btnValue == UP)
    {
        motorCtrl.MotorForward(2500);
        delay(500);
        motorCtrl.MotorOff();
    }
    else if (btnValue == DOWN)
    {
        motorCtrl.MotorBackward(1250);
        delay(500);
        motorCtrl.MotorOff();
    }
    else if (btnValue == LEFT)
    {
        motorCtrl.MotorOff();
        delay(100);
        motorCtrl.MotorTurn(0, 15);
    }
    else if (btnValue == RIGHT)
    {
        motorCtrl.MotorOff();
        delay(100);
        motorCtrl.MotorTurn(1, 15);
    }
    else if (btnValue == SELECT)
    {
        motorCtrl.MotorOff();
    }
    if(btnValue==6){
      dist_stop();
    }
    //Serial.println(btnValue);
    if(n1==12){
        clearSerialBuffer();
        n1 = 0;
    }
      
   // delay(100);
}
int read_data()
{
    if (mySerial.available() > 0) {
        String receivedString = mySerial.readStringUntil('\n');
        char firstChar = receivedString.charAt(0);
        if (firstChar >= '0' && firstChar <= '9') {
            int receiveInt = firstChar - '0';
            return receiveInt;
        }
        //return 0; 
    }
    return (-1);
}
void clearSerialBuffer() {
  while (mySerial.available() > 0) {
    char t = mySerial.read();
    // 不做任何处理，仅仅清空缓冲区
  }
}


void dist_back(){
  for (int i = 0; i < 100; i++) { // Loop to get 100 distance values per second
    // Send the command to get the distance measurement result
    Wire.beginTransmission(DEPTH_CAMERA_ADDRESS);
    Wire.write(0x5A);
    Wire.write(0x05);
    Wire.write(0x00);
    Wire.write(0x01);
    Wire.write(0x60);
    Wire.endTransmission();

    // Small delay to allow the camera to process the command
    delayMicroseconds(100); // 根据相机处理时间调整，100微秒延迟是个合理的初始值

    // Request 9 bytes from the depth camera
    Wire.requestFrom(DEPTH_CAMERA_ADDRESS, 9);

    // Check if the data is available
    if (Wire.available() == 9) {
      uint8_t data[9];
      for (int i = 0; i < 9; i++) {
        data[i] = Wire.read();
      }

      // Verify the frame header
      if (data[0] == 0x59 && data[1] == 0x59) {
        // Calculate the checksum
        uint8_t checksum = 0;
        for (int i = 0; i < 8; i++) {
          checksum += data[i];
        }

        // Verify the checksum
        if (checksum == data[8]) {
          // Parse the distance
          int16_t distance = (data[3] << 8) | data[2];

          // Print the distance value
          //Serial.print("Distance: ");
          //Serial.print(distance);
          //Serial.println(" cm");
          dist_array[count] = distance;
          count++;
          if(count==n){
            double average = 0;
            for (int j = 0; j < n; j++) {
                average += dist_array[j];
            }
            average /= n; // 计算平均数
            Serial.println(average);
            if (average<40){
              motorCtrl.MotorTurn(0, 130);
              left_count++;
              startTime = millis();
              Serial.print("Left");
            }else if (average>=40 && left_count <= 0){
              elapsedTime_right = millis() - startTime;
              if(right_count<=0 || elapsedTime_right<9200){
              motorCtrl.MotorForward(3000);
              Serial.print("Up");}
              else{
              motorCtrl.MotorTurn(0, 130);
              right_count -= 4;
              if(right_count<=0){
                right_count=0;
                left_count = 0;
                startTime = millis();
              }
              }
            }else if (average>=40 && left_count > 0){
               elapsedTime = millis() - startTime;
              if (elapsedTime < 4000){
                if(ano_left>0){
                  motorCtrl.MotorTurn(0, 60);
                  ano_left--;
                }
                    motorCtrl.MotorForward(3000);
                    Serial.print("Up");
              }else{
                    motorCtrl.MotorTurn(1, 130);
                    Serial.print("Right"); 
                    left_count -= 0.3;
                    if(left_count<=0){
                      left_count = 0;
                    }
                    right_count++;
              }
            }
            // 清空数组，重置count
            for (int i = 0; i < n; i++) {
                dist_array[i] = 0;
            }
            count = 0;
          }
        } else {
          Serial.println("Checksum error.");
        }
      } else {
        Serial.println("Frame header error.");
      }
    } else {
      Serial.println("Failed to read data from depth camera.");
    }

    // Wait for a short while before the next request
    delayMicroseconds(9000); // Adjust this delay to achieve 100 samples per second
  }

  // Wait for the remaining time to complete one second
  delay(1000 - (100 * 10)); // Subtract the time already spent in microseconds (100 samples * 10 ms)
}


void dist_stop(){
  for (int i = 0; i < 100; i++) { // Loop to get 100 distance values per second
    // Send the command to get the distance measurement result
    Wire.beginTransmission(DEPTH_CAMERA_ADDRESS);
    Wire.write(0x5A);
    Wire.write(0x05);
    Wire.write(0x00);
    Wire.write(0x01);
    Wire.write(0x60);
    Wire.endTransmission();

    // Small delay to allow the camera to process the command
    delayMicroseconds(100); // 根据相机处理时间调整，100微秒延迟是个合理的初始值

    // Request 9 bytes from the depth camera
    Wire.requestFrom(DEPTH_CAMERA_ADDRESS, 9);

    // Check if the data is available
    if (Wire.available() == 9) {
      uint8_t data[9];
      for (int i = 0; i < 9; i++) {
        data[i] = Wire.read();
      }

      // Verify the frame header
      if (data[0] == 0x59 && data[1] == 0x59) {
        // Calculate the checksum
        uint8_t checksum = 0;
        for (int i = 0; i < 8; i++) {
          checksum += data[i];
        }

        // Verify the checksum
        if (checksum == data[8]) {
          // Parse the distance
          int16_t distance = (data[3] << 8) | data[2];

          // Print the distance value
          //Serial.print("Distance: ");
          //Serial.print(distance);
          //Serial.println(" cm");
          dist_array[count] = distance;
          count++;
          if(count==n){
            double average = 0;
            for (int j = 0; j < n; j++) {
                average += dist_array[j];
            }
            average /= n; 
            Serial.println(average);
            if (average<35 && average>30){
              motorCtrl.MotorOff();
              Serial.println("power off");
            }
            else if (average>=35){
              motorCtrl.MotorForward(1800);
              Serial.println("UP");
              }
            else{
              motorCtrl.MotorBackward(1800);
              Serial.println("DOWN");

              }
            // 清空数组，重置count
            for (int i = 0; i < n; i++) {
                dist_array[i] = 0;
            }
            count = 0;
          }
        } else {
          Serial.println("Checksum error.");
        }
      } else {
        Serial.println("Frame header error.");
      }
    } else {
      Serial.println("Failed to read data from depth camera.");
    }

    // Wait for a short while before the next request
    delayMicroseconds(9000); // Adjust this delay to achieve 100 samples per second
  }

  // Wait for the remaining time to complete one second
  delay(1000 - (100 * 10)); // Subtract the time already spent in microseconds (100 samples * 10 ms)
}
// int read_LCD_buttons()
// {
//     int adcData = analogRead(0);
//     if (adcData < 50)
//         return UP;
//     else if (adcData < 400)
//         return RIGHT;
//     else if (adcData < 450)
//         return SELECT;
//     else if (adcData < 500)
//         return DOWN;
//     else if (adcData < 550)
//         return LEFT;
//     else
//         return NONE;
// }