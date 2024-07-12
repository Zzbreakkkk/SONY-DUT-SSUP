// v3版本，只识别一种颜色
#include <SPI.h>
#include <Camera.h>
#include <Adafruit_ILI9341.h>
#include <Adafruit_GFX.h>
#include <SDHCI.h>
#include <DNNRT.h>

#define TFT_CS -1 
#define TFT_RST 8 
#define TFT_DC  9
// Adafruit_ILI9341 display = Adafruit_ILI9341(TFT_CS, TFT_DC);
Adafruit_ILI9341 display = Adafruit_ILI9341(&SPI, TFT_DC, TFT_CS, TFT_RST);
SDClass theSD;
typedef struct{
  int16_t s_sx;
  int16_t s_sy;
  int Rect_width;
  int Rect_height;
}Rect;
#define OFFSET_X  (48)
#define OFFSET_Y  (6)
#define CLIP_WIDTH  (224)
#define CLIP_HEIGHT  (224)
#define DNN_WIDTH  (28)
#define DNN_HEIGHT  (28)

//新加的
#define CAM_IMG_W 320
#define CAM_IMG_H 240
#define CAM_CLIP_X 104
#define CAM_CLIP_Y 50
#define CAM_CLIP_W 90
#define CAM_CLIP_H 90
#define LINE_THICKNESS 5
#define arr_len    5

DNNRT dnnrt;
SDClass SD;
// 输入RGB图像
DNNVariable input(DNN_WIDTH*DNN_HEIGHT*3);  

void draw_static_box(uint16_t* imgBuf){
  //绘制图像框的上下边界
  for(int x = CAM_CLIP_X; x<CAM_CLIP_X+CAM_CLIP_W; ++x){
    //此层for循环用来绘制线条的厚度
    for(int n = 0; n < LINE_THICKNESS;++n){
      //计算了从图像缓冲区起始位置到当前行的偏移量。这相当于将 n 行加到 CAM_CLIP_Y 上，然后乘以 CAM_IMG_W 得到字节偏移量。
      *(imgBuf + CAM_IMG_W*(CAM_CLIP_Y+n) + x)              =ILI9341_PINK;
      *(imgBuf + CAM_IMG_W*(CAM_CLIP_Y+CAM_CLIP_H-1-n) + x) =ILI9341_PINK;
    }
  }

  for(int y = CAM_CLIP_Y; y<CAM_CLIP_Y+CAM_CLIP_H; ++y){
    for(int n = 0; n < LINE_THICKNESS;++n){
      *(imgBuf + CAM_IMG_W*y + CAM_CLIP_X+n)                =ILI9341_PINK;
      *(imgBuf + CAM_IMG_W*y + CAM_CLIP_X + CAM_CLIP_W-1-n) =ILI9341_PINK;
    }
  }
}

//传输图片
void Transmitted_image(uint16_t* buf,int length){
  for(int i=0;i<length; ++i, ++buf){
    Serial.write(*buf);
  }
}

void CamCB(CamImage img) 
{
  unsigned long start_time, end_time, elapsedTime;
  start_time = millis();

  if (!img.isAvailable()) 
  {
    // Serial.println("333");
    return;
  }

  // 图像的剪切和缩小
  CamImage small; 
  CamErr camErr = img.clipAndResizeImageByHW(small
            ,OFFSET_X ,OFFSET_Y 
            ,OFFSET_X+CLIP_WIDTH-1 ,OFFSET_Y+CLIP_HEIGHT-1 
            ,DNN_WIDTH ,DNN_HEIGHT);
  if (!small.isAvailable()) return;

  // 将图像从YUV转换为RGB565
  small.convertPixFormat(CAM_IMAGE_PIX_FMT_RGB565); 
  uint16_t* sbuf = (uint16_t*)small.getImgBuff();

  // 将RGB像素分割成帧
  float* fbuf_r = input.data();
  float* fbuf_g = fbuf_r + DNN_WIDTH*DNN_HEIGHT;
  float* fbuf_b = fbuf_g + DNN_WIDTH*DNN_HEIGHT;
  for (int i = 0; i < DNN_WIDTH*DNN_HEIGHT; ++i) {
   fbuf_r[i] = (float)((sbuf[i] >> 11) & 0x1F)/31.0; // 0x1F = 31
   fbuf_g[i] = (float)((sbuf[i] >>  5) & 0x3F)/63.0; // 0x3F = 64
   fbuf_b[i] = (float)((sbuf[i])       & 0x1F)/31.0; // 0x1F = 31
  }
  
  unsigned long start_dnnrttime, end_dnnrttime, elapseddnnrtTime;
  start_dnnrttime = millis();

  // 执行推论  执行推理，执行推理
  dnnrt.inputVariable(input, 0);
  dnnrt.forward();
  DNNVariable output = dnnrt.outputVariable(0); //output:全是小数的数组

  // end_dnnrttime = millis();
  // elapseddnnrtTime = end_dnnrttime - start_dnnrttime;
  // Serial.print("Dnnrt已经过的时间: ");
  // Serial.print(elapseddnnrtTime);
  // Serial.println(" 毫秒");
  

  // Serial.println("dnnrt is ok");

  // 将DNNRT的结果成像以输出到LCD上
  static uint16_t result_buf[DNN_WIDTH*DNN_HEIGHT];
  for (int i = 0; i < DNN_WIDTH * DNN_HEIGHT; ++i) {
    uint16_t value = output[i] * 0x3F; // 6bit
    if (value > 0x3F) value = 0x3F;
    result_buf[i] = (value << 5);  // Only Green
  }
  //获取识别对象的横向宽度和横向坐标

  // 一些必要的局部变量
  int sx1, width1, sy1, height1;
  int allNegativeOne = 1;
  // String ss1;
  sx1 = width1 = sy1 = height1 = 0;

  //定义颜色缓存数组
  char *color_array = NULL;
  int array_size = 0;

  //定义用于串口通信的数组，全置为-1
  //int *arr = (int*)malloc(sizeof(int)*20);
  int *arr = (int*)malloc(sizeof(int)*5);
  for (int i = 0; i < arr_len; i++) {
    arr[i] = -1;
  }

  // Serial.println("131 line");

  //定义结构体类型指针，接受传过来的参数
  Rect *rect_list;
  rect_list = get_sx_and_sy_width_height_of_region(output,DNN_WIDTH,DNN_HEIGHT);
  // Serial.println("get_sx_and_sy_width_height_of_region is ok");
  if(rect_list == NULL){
    Serial.println("rect is NULL……");
  }

  // Serial.println("---------------------------------------------------------------");
  // 什么都没检测出来
  //if ((rect_list[0].Rect_width == 0 && rect_list[0].Rect_height == 0) && (rect_list[1].Rect_width == 0 && rect_list[1].Rect_height == 0 ) && (rect_list[2].Rect_width == 0 && rect_list[2].Rect_height == 0) && (rect_list[3].Rect_width == 0 && rect_list[3].Rect_height == 0)) {
  if ((rect_list[0].Rect_width == 0 && rect_list[0].Rect_height == 0)) {
    goto disp;
  }
  
  if(rect_list[0].Rect_width > 0 && rect_list[0].Rect_height > 0){
    // 根据相机图像放大认证对象的方框和坐标
    sx1 = rect_list[0].s_sx * (CLIP_WIDTH/DNN_WIDTH) + OFFSET_X;
    width1 = rect_list[0].Rect_width * (CLIP_WIDTH/DNN_WIDTH);
    sy1 = rect_list[0].s_sy * (CLIP_HEIGHT/DNN_HEIGHT) + OFFSET_Y;
    height1 = rect_list[0].Rect_height * (CLIP_HEIGHT/DNN_HEIGHT);
  }

  
disp:
  img.convertPixFormat(CAM_IMAGE_PIX_FMT_RGB565);  
  uint16_t* buf = (uint16_t*)img.getImgBuff(); 
  
  //在相机图像上绘制识别框,判断是否识别到物体，识别到了才画框，否则不画
  //并且识别到了之后才会在arr数组中赋值，没有识别到的，就不赋值。
  if(rect_list[0].Rect_width > 0 && rect_list[0].Rect_height > 0)
  {
    char color1 = 'R';
    //判断颜色下标，并更改arr数组内容，下同
    int is_draw_box_id = Determine_color_index(color1, arr, sx1, sy1, width1, height1);
    if(is_draw_box_id != -1)
    {
      draw_box(buf, sx1, sy1, width1, height1);
    }

    
  }



  if(arr[0] != -1)
  {
    data_transmission_plus(arr);
  }
  

  // 在帧缓冲器中绘制边带
  draw_sideband(buf, OFFSET_X, ILI9341_BLACK);
    
  // 在LCD的左上方显示DNNRT的输入图像
  display.drawRGBBitmap(0, 0, (uint16_t*)sbuf, DNN_HEIGHT, DNN_WIDTH);  
  // DNNRT的输出图像显示在LCD的右上角
  display.drawRGBBitmap(320-DNN_WIDTH, 0, result_buf, DNN_WIDTH, DNN_HEIGHT);  
  // 显示
  display.drawRGBBitmap(0, DNN_HEIGHT, buf, 320, 240-DNN_HEIGHT);

  //释放内存
  free(rect_list);
  free(arr);
  free(color_array);

  // end_time = millis();
  // elapsedTime = end_time - start_time;
  // Serial.print("整体已经过的时间: ");
  // Serial.print(elapsedTime);
  // Serial.println(" 毫秒");
}


void setup() {
  Serial.begin(115200);
  Serial2.begin(115200);
  display.begin(40000000);
  display.setRotation(3);
  display.fillRect(0, 0, 320, 240, ILI9341_BLUE);
  while(!theSD.begin()) 
  {                                                                                                                                                                                                                                                                                                                                                     
      Serial.println("Insert SD card!!!");
  }
  File nnbfile = SD.open("red_block_model.nnb");
  if (!nnbfile) {
    Serial.print("nnb not found");
    return;
  }

  Serial.println("DNN initialize");
  int ret = dnnrt.begin(nnbfile);
  if (ret < 0) {
    Serial.print("Runtime initialization failure. ");
    Serial.println(ret);
    return;
  }
  theCamera.begin();
  theCamera.startStreaming(true, CamCB);
}

void loop() {
  // put your main code here, to run repeatedly:

}
