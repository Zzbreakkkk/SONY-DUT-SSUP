
#define RX_MAX_BUF 8

//接收数据相关变量
uint8_t Rx_Data[8] = {0};
uint8_t Rx_index = 0;
uint8_t Rx_Flag = 0;
uint8_t RecvFlag = 0;

// 舵机定时运行变量
uint64_t time_run = 0;


/* 控制总线舵机，
 * id：要控制的id号，0xfe为全体控制
 * value：位置值（96~4000） 
 * time：运行的时间，时间越小，运行越快，最小为0 
 * */
void bus_servo_control(int id, int value, int time)
{
    uint8_t head1 = 0xff;
    uint8_t head2 = 0xff;
    uint8_t s_id = id & 0xff;
    uint8_t len = 0x07;
    uint8_t cmd = 0x03;
    uint8_t addr = 0x2a;

    if (value > 4000)
        value = 4000;
    else if (value < 96)
        value = 96;

    uint8_t pos_H = (value >> 8) & 0xff;
    uint8_t pos_L = value & 0xff;

    uint8_t time_H = (time >> 8) & 0xff;
    uint8_t time_L = time & 0xff;

    uint8_t checknum = (~(s_id + len + cmd + addr +
                          pos_H + pos_L + time_H + time_L)) & 0xff;
    uint8_t data[] = {head1, head2, s_id, len, cmd,
                      addr, pos_H, pos_L, time_H, time_L, checknum};

    Serial2.write(data, 11);
}

/* 写入目标ID(1~250) */
void bus_servo_set_id(uint8_t id)
{
    if ((id >= 1) && (id <= 250))
    {
        uint8_t head1 = 0xff;
        uint8_t head2 = 0xff;
        uint8_t s_id = 0xfe; /* 发送广播的ID */
        uint8_t len = 0x04;
        uint8_t cmd = 0x03;
        uint8_t addr = 0x05;
        uint8_t set_id = id; /* 实际写入的ID */

        uint8_t checknum = (~(s_id + len + cmd + addr + set_id)) & 0xff;
        uint8_t data[] = {head1, head2, s_id, len, cmd, addr, set_id, checknum};

        Serial2.write(data, 8);
    }
}

/* 发送读取舵机位置命令 */
void bus_servo_read(uint8_t id)
{
    uint8_t head1 = 0xff;
    uint8_t head2 = 0xff;
    uint8_t s_id = id & 0xff;
    uint8_t len = 0x04;
    uint8_t cmd = 0x02;
    uint8_t param_H = 0x38;
    uint8_t param_L = 0x02;

    uint8_t checknum = (~(s_id + len + cmd + param_H + param_L)) & 0xff;
    uint8_t data[] = {head1, head2, s_id, len, cmd, param_H, param_L, checknum};

    Serial2.write(data, 8);
}

//转化接收到的值为位置数
uint16_t bus_servo_get_value(void)
{
    uint8_t checknum = (~(Rx_Data[2] + Rx_Data[3] + Rx_Data[4] + Rx_Data[5] + Rx_Data[6])) & 0xff;
    if(checknum == Rx_Data[7])
    {
        uint8_t s_id = Rx_Data[2];
        uint16_t value_H = 0;
        uint16_t value_L = 0;

        value_H = Rx_Data[5];
        value_L = Rx_Data[6];
        uint16_t value = (value_H << 8) + value_L;
        return value;
    }
    return 0;
}

//处理串口数据，如果符合协议则设置RecvFlag = 1
void bus_servo_uart_recv(uint8_t Rx_Temp)
{
    switch(Rx_Flag)
    {
        case 0:
            if(Rx_Temp == 0xff)
            {
                Rx_Data[0] = 0xff;
                Rx_Flag = 1;
            }
            else if (Rx_Temp == 0xf5)
            {
                Rx_Data[0] = 0xff;
                Rx_Data[1] = 0xf5;
                Rx_Flag = 2;
                Rx_index = 2;
            }
            break;
            Serial.print('case 0');

        case 1:
            if(Rx_Temp == 0xf5)
            {
                Rx_Data[1] = 0xf5;
                Rx_Flag = 2;
                Rx_index = 2;
            } else
            {
                Rx_Flag = 0;
                Rx_Data[0] = 0x0;
            }
            break;
            Serial.print('case 1');

        case 2:
            Rx_Data[Rx_index] = Rx_Temp;
            Rx_index++;

            if(Rx_index >= RX_MAX_BUF)
            {
                Rx_Flag = 0;
                RecvFlag = 1;
            }
            break;
            Serial.print('case 2');

        default:
            break;
    }
}

void setup()
{
    Serial.begin(115200);
    Serial2.begin(115200);
    // 初始化每个舵机的ID，不要设置
    // bus_servo_set_id(1);
    // bus_servo_set_id(2);
    // bus_servo_set_id(3);
    // bus_servo_set_id(4);
    // bus_servo_set_id(5);
    delay(10);
}

void loop()
{
    
    if (RecvFlag)
    {
        uint16_t value = bus_servo_get_value();
        if (value)
        {
            Serial.print("\r\nvalue=");
            Serial.println(value);
        }
        else
        {
            Serial.println("\r\nread error");
        }
        RecvFlag = 0;
    }

    定时2秒钟运行一次
    if (millis() - time_run >= 2000)
    {
        static int state = 1;
        if (state)
        {
            bus_servo_control(0x01, 2400, 1000);
            delay(1000);
            bus_servo_control(0x02, 2400, 1000);
            delay(1000);
            bus_servo_control(0x03, 2400, 1000);
            delay(1000);
            bus_servo_control(0x04, 2400, 1000);
            delay(1000);
            bus_servo_control(0x05, 2400, 1000);
            delay(1000);
            bus_servo_control(0x06, 2400, 1000);
            delay(1000);
            state = 0;
        }
        else
        {
            bus_servo_control(0x06, 2000, 1000);
            delay(1000);
            bus_servo_control(0x05, 2000, 1000);
            delay(1000);
            bus_servo_control(0x04, 2000, 1000);
            delay(1000);
            bus_servo_control(0x03, 2000, 1000);
            delay(1000);
            bus_servo_control(0x02, 2000, 1000);
            delay(1000);
            bus_servo_control(0x01, 2000, 1000);
            delay(1000);
            state = 1;
        }
        time_run = millis();
        bus_servo_read(1);
    }

    

    }
    

    // while (Serial2.available())
    // {
    //     uint8_t RXTemp = (uint8_t)Serial2.read();
    //     Serial.println(RXTemp,HEX);
    //     bus_servo_uart_recv(RXTemp);
    //     delay(1);
    // }
    
    delay(1);
}


// //串口中断
// void serialEvent()
// {
//     while (Serial2.available())
//     {
//         uint8_t RXTemp = (uint8_t)Serial2.read();
//         Serial.println(RXTemp);
//         bus_servo_uart_recv(RXTemp);
//         // Serial.write(&RXTemp, 1);
//         delay(1);
//     }
// }