#include "PCA9685.h"
#include "Motor.hh"

#define SELECT 0
#define LEFT 1
#define RIGHT 2
#define UP 3
#define DOWN 4
#define NONE 5

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

int uart[9];  //save data measured by LiDAR
const int HEADER=0x59;  //frame header of data package


void setup() {
  Serial.begin(115200); //set bit rate of serial port connecting Arduino with computer
  Serial2.begin(115200,SERIAL_8N1);  //set bit rate of serial port connecting LiDAR with Arduino
  Wire.begin();
  pwmController.resetDevices();
  pwmController.init();
  pwmController.setPWMFrequency(500);
}

void loop() { 
  if (Serial2.available()) {  //check if serial port has data input
    if(Serial2.read() == HEADER) {  //assess data package frame header 0x59
      uart[0]=HEADER;
      if (Serial2.read() == HEADER) { //assess data package frame header 0x59
        uart[1] = HEADER;
        for (i = 2; i < 9; i++) { //save data in array
          uart[i] = Serial2.read();
          delay(1);
        }
        check = uart[0] + uart[1] + uart[2] + uart[3] + uart[4] + uart[5] + uart[6] + uart[7];
        if (uart[8] == (check & 0xff)){ //verify the received data as per protocol
          dist = uart[2] + uart[3] * 256;     //calculate distance value
          dist_array[count] = dist;
          count++;
          if(count==n){
            double average = 0;
            for (int j = 0; j < n; j++) {
                average += dist_array[j];
            }
            average /= n; // 计算平均数
            Serial.println(average);
            if (average<35){
              motorCtrl.MotorTurn(0, 65);
              left_count++;
              startTime = millis();
              Serial.print("Left");
            }else if (average>=35 && left_count <= 0){
              elapsedTime_right = millis() - startTime;
              if(right_count<=0 || elapsedTime_right<4500){
              motorCtrl.MotorForward(3200);
              Serial.print("Up");}
              else{
              motorCtrl.MotorTurn(0, 65);
              right_count -= 3.4;
              if(right_count<=0){
                right_count=0;
                left_count = 0;
                startTime = millis();
              }
              }
            }else if (average>=35 && left_count > 0){
               elapsedTime = millis() - startTime;
              if (elapsedTime < 1500){
                    motorCtrl.MotorForward(3200);
                    Serial.print("Up");
              }else{
                    motorCtrl.MotorTurn(1, 65);
                    Serial.print("Right"); 
                    left_count -= 0.4;
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
        }
      }
    }
  }
  }