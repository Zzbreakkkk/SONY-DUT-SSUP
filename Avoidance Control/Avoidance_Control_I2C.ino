#include <Wire.h>
#include "PCA9685.h"
#include "Motor.hh"

// I2C address of the depth camera
#define DEPTH_CAMERA_ADDRESS 0x10

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

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  Serial2.begin(115200,SERIAL_8N1);
  // Initialize I2C communication
  Wire.begin();
  pwmController.resetDevices();
  pwmController.init();
  pwmController.setPWMFrequency(500);
  // Print a message to indicate setup is complete
  //Serial.println("I2C setup complete. Ready to communicate with the depth camera.");
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

void loop() {
  dist_stop();
}
