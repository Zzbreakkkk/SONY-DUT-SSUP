#define IMG_WIDTH  (320)
#define IMG_HEIGHT  (240)
#define THICKNESS (4)

typedef struct {
    unsigned int red : 5;
    unsigned int green : 6;
    unsigned int blue : 5;
}RGB565Color;

void draw_sideband(uint16_t* buf, int thickness, int color) {
  for (int i = 0; i < IMG_HEIGHT; ++i) {
    for (int j = 0; j < thickness; ++j) {
      buf[i*IMG_WIDTH + j] = color;
      buf[i*IMG_WIDTH + IMG_WIDTH-j-1] = color;
    }
  } 
}

bool draw_box(uint16_t* buf, int sx, int sy, int w, int h) {
  const int thickness = 4; // BOX线的粗细
  
  if (sx < 0 || sy < 0 || w < 0 || h < 0) { 
    Serial.println("draw_box parameter error");
    return false;
  }
  if (sx+w >= OFFSET_X+CLIP_WIDTH) 
    w = OFFSET_X+CLIP_WIDTH-sx-1;
  if (sy+h >= OFFSET_Y+CLIP_HEIGHT) 
    h = OFFSET_Y+CLIP_HEIGHT-sy;
  
  /* 画出正方形的水平线 */
  for (int j = sx; j < sx+w; ++j) {
    for (int n = 0; n < thickness; ++n) {
      buf[(sy+n)*IMG_WIDTH + j] = ILI9341_PINK;
      buf[(sy+h-n)*IMG_WIDTH + j] = ILI9341_PINK;
    }
  }
  /* 绘制正方形的垂直线 */
  for (int i = sy; i < sy+h; ++i) {
    for (int n = 0; n < thickness; ++n) { 
      buf[i*IMG_WIDTH+sx+n] = ILI9341_PINK;
      buf[i*IMG_WIDTH+sx+w-n] = ILI9341_PINK;
    }
  }
  return true;
}

void data_transmission(int sx, int sy, int width, int height)
{
  // 尝试传输坐标数据
  String head = "Data,";
  // 将坐标数据转换为字符串
  String coordinates = head + String(sx) + "," + String(sy) + "," + String(width) + "," + String(height);
  //发送数据到串口
  if(!Serial.println(coordinates))
  {
      Serial.println("data put fail……");
      Serial.end();  // 关闭串口
  }
}

void data_transmission_plus(int arr[])
{
  int t_c = turn_command(arr[1],arr[3]);//转向
  Serial.println(t_c);
  Serial2.println(String(t_c));
  //delay(1000);
  if(t_c==5){
    int f_c = forward_command(arr[3],arr[4]); //前进
    Serial.println(f_c);
    Serial2.println(String(f_c));
  }
  
  //delay(1000);
  String arr_result = "Data," + String(arr[0]) + "," + String(arr[1]) + "," + String(arr[2]) + ","  + String(arr[3]) + "," + String(arr[4]);
  
  // String arr_result = "Data," + String(arr[0]) + "," + String(arr[1]) + "," + String(arr[2]);
  //发送数据到串口
  if(!Serial.println(arr_result))
  {
      Serial.println("data put fail……");
      Serial.end();  // 关闭串口
  }
}
int forward_command(int width, int height){
    //int mid = 120;
    //int w_small = 40;  //远距离阈值，宽  
    int w_big = 120; 
    Serial.println(width);   //近距离阈值，宽
    if(width<w_big)
      return 0;   //前进
    return 5;
    
}
int turn_command(int sx,int width){
    //int mid = 120;
    //int w_small = 40;  //远距离阈值，宽  
    int mid = 160 - 0.5*width;  //中线
    if(sx<mid-20)
      return 1;  //左转
    if(sx>mid+20)   
      return 2;  //右转
    return 5;
}
// 根据RGB565值转换为RGB颜色值
void convertRGB565toRGB(unsigned int rgb565, unsigned char* red, unsigned char* green, unsigned char* blue) {
    RGB565Color color;
    color.red = (rgb565 >> 11) & 0x1F;
    color.green = (rgb565 >> 5) & 0x3F;
    color.blue = rgb565 & 0x1F;

    *red = (color.red << 3) | (color.red >> 2);
    *green = (color.green << 2) | (color.green >> 4);
    *blue = (color.blue << 3) | (color.blue >> 2);
}

// 判断颜色属于红、黄、蓝、绿中的哪一种
char classifyColor(unsigned char red, unsigned char green, unsigned char blue) {
    // if (red > green && red > blue) {
    if (red > 120 && red < 255) { //原150
        if (green < 100 && blue < 100) {
            return 'R'; // 红色
        }
        if (green > 150 && blue < 100) {
            return 'Y'; // 黄色
        }
    }
    // if (green > red && green > blue) {
    if (green > 110 && green < 255) {
        if (red < 100 && blue < 100) {
            return 'G'; // 绿色
        }
    }
    // if (blue > red && blue > green) {
    if (blue > 110 && blue < 255) {
        if (red < 100 && green < 100) {
            return 'B'; // 蓝色
        }
    }
    return 'N'; // 未知颜色
}

char find_Max_Color(unsigned int colorCounts[]){
  //unsigned int max = -1;//传进来的参数值至少为0，所以返回值至少为0，不会出现-1和其他歧义
  int max_idx = 0;
  int length = 5;
  for(int i=0;i<length;i++){
    if(colorCounts[i] > colorCounts[max_idx]){
      max_idx = i;
    }
  }
  // Serial.print("max_idx is: ");
  // Serial.println(max_idx);
  if(max_idx == 1)
    return 'R';
  else if(max_idx == 2)
    return 'Y';
  else if(max_idx == 3)
    return 'B';
  else if(max_idx == 4)
    return 'G';
  else
    return 'N';//如果全为0，那么就是该是别的颜色都没有识别到，则返回空
}

char recognizeColorInRectangle(uint16_t* imgBuf, int sx, int sy, int width, int height)
{
  // 统计颜色出现的频率
  unsigned int colorCounts[5] = {0}; // 红、黄、蓝、绿,空
  for(int x = sy + THICKNESS + 1; x < sy + height - THICKNESS - 1; ++x)
  {
    for(int y = sx + THICKNESS + 1; y < sx + width - THICKNESS - 1; ++y)
    {
      //原先的
      unsigned int pixelValue  = *(imgBuf + IMG_WIDTH * x + y);
      unsigned char red, green, blue;
      convertRGB565toRGB(pixelValue, &red, &green, &blue);

      char color = classifyColor(red, green, blue);
      switch (color)
      {
        case 'R':
            colorCounts[1]++; // 红色
            break;
        case 'Y':
            colorCounts[2]++; // 黄色
            break;
        case 'B':
            colorCounts[3]++; // 蓝色
            break;
        case 'G':
            colorCounts[4]++; // 绿色
            break;
      }
    }    
  }
 
  char mostFrequentColor = find_Max_Color(colorCounts); 
  return mostFrequentColor;  
}

int Determine_color_index(char color, int *arr, int sx, int sy,int width, int height)
{
  switch(color)
  {
    case 'R':
      arr[0] = 0;
      arr[1] = sx;
      arr[2] = sy;
      arr[3] = width;
      arr[4] = height;
      return 0;
      break;
      
    // case 'Y':
    //   arr[0] = 1;
    //   arr[1] = sx;
    //   arr[2] = sy;
    //   arr[3] = width;
    //   arr[4] = height;
    //   return 5;
    //   break;
    // case 'B':
    //   arr[0] = 2;
    //   arr[1] = sx;
    //   arr[2] = sy;
    //   arr[3] = width;
    //   arr[4] = height;
    //   return 10;
    //   break;
    // case 'G':
    //   arr[0] = 3;
    //   arr[1] = sx;
    //   arr[2] = sy;
    //   arr[3] = width;
    //   arr[4] = height;
    //   return 15;
    //   break;
    default:
      return -1; //如果什么颜色都没有，则就是-1
  }
}

void insert_color(char color, char** color_array, int* array_size)
{
  //动态分配更大内存
  (*array_size)++;
  *color_array = (char*)realloc(*color_array, *array_size * sizeof(char));

  // 将颜色插入到数组的尾部
  (*color_array)[*array_size - 1] = color;
}

bool check_duplicate_color(char color, char* color_array, int array_size)
{
  for(int i=0;i<array_size;i++)
  {
    if(color == color_array[i])
      return true;
  }
  return false;
}




