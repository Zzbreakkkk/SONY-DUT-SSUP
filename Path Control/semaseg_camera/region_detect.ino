#include<microTuple.h>
//#include <Rect_struct.h>

// #ifndef RECT_STRUCT_H
// #define RECT_STRUCT_H
// //创建搜索结构体

// #endif

// 记录像素的连续值的阈值
const float threshold = 0.8;
const int   rectThreshold = 2;

// 更改后的方法
Rect *get_sx_and_sy_width_height_of_region(DNNVariable &output, int w, int h)
{
  // Serial.println("region 128");
  //自变量检查
  if (&output == NULL || w <= 0 || h <= 0) {
    Serial.println(String(__FUNCTION__) + ": param error");
    return NULL;
  }
  
  // 初始化 设置变量
  int16_t s_sx, s_sy;
  int s_width, s_height;
  int max_w = -1;
  int max_h = -1;
  int index = 0;//数组中结构体信息下标
  
  int16_t max_h_val = -1;  // 最大宽度(水平方向)
  int16_t max_h_point = -1; // 最大宽度的结束坐标
  int max_v_val = -1;  // 最大幅（高さ方向）を格納
  int max_v_point = -1;  // 最大高さの終了座標

  //开辟一个新的掩码，和output一模一样
  float *out_put_mask = (float*)malloc(w*h*sizeof(float));
  // memset(out_put_mask, 0, w*h*sizeof(float));//设置内存
  
  // Serial.println("region 45");

  for (int i = 0; i < h; ++i) 
  {
    for (int j = 0; j < w; ++j) {
      out_put_mask[i*w+j] = output[i*w+j]; // 将相同的内容复制到一个新的掩码中，后续对这个掩码进行修改，
                                            //因为output的东西只能读，没有修改的权限
    }
  }
  // Serial.println("region 54");
  // 表示最多有四个框
  // Rect *rect_list = (Rect*)malloc(sizeof(Rect) * 4);
  Rect *rect_list = (Rect*)malloc(sizeof(Rect));

  // Serial.println("region 59");
  
  if(rect_list == NULL){
    Serial.println("Memory allocation failure……");
  }
  

  // 确保地图用内存   
  uint16_t *h_integ = (uint16_t*)malloc(w*h*sizeof(uint16_t));
  memset(h_integ, 0, w*h*sizeof(uint16_t));//设置内存

  // 确保地图用内存   
  uint16_t *v_integ = (uint16_t*)malloc(w*h*sizeof(uint16_t));
  memset(v_integ, 0, w*h*sizeof(uint16_t));
  
  
  // 求宽度
  // 创建一个横向连续值的图
  for (int i = 0; i < h; ++i) {
    int h_val = 0;
    for (int j = 0; j < w; ++j) {
      // 当像素的输出高于阈值时
      if (out_put_mask[i*w+j] > threshold) ++h_val;
      else h_val = 0; // 阈值以下为0复位
      h_integ[i*w+j] = h_val; // 添加到地图
      if(h_val > max_h_val)
      {
        max_h_val = h_val;
        s_sx = j - h_val + 1;//起始坐标(x)
        s_width = h_val;
      }
    }
  }

  // for (int i = 0; i < h; ++i) {
  //   for (int j = 0; j < w; ++j) {
  //     if (h_integ[i*w+j] > max_h_val) {
  //       max_h_val = h_integ[i*w+j]; // 图中存储的连续值
  //       max_h_point = j; // 连续值结束的坐标值
  //     }
  //   }
  // }
  // s_sx = max_h_point - max_h_val; // 起始坐标(x)
  // s_width = max_h_val; // 最大区域的宽度

  // 求高度
  // 创建纵向连续值的图
  for (int j = 0; j < w; ++j) {
    int v_val = 0;
    for (int i = 0; i < h; ++i) {
      // ピクセルの出力が閾値より上の場合は加算     
      if (out_put_mask[i*w+j] > threshold) ++v_val;
      else v_val = 0;  // 閾値以下は0リセット
      v_integ[i*w+j] = v_val; // マップに追加
      if (v_val > max_v_val) {
        max_v_val = v_val;
        s_sy = i - v_val + 1;
        s_height = v_val;
      }
    }
  }

  // // // マップの最大値を探し、最大領域の縦幅と終端座標を得る
  // for (int j = 0; j < w; ++j) {
  //   for (int i = 0; i < h; ++i) {
  //     if (v_integ[i*w+j] > max_v_val) {
  //       max_v_val = v_integ[i*w+j];  // マップに格納された連続値
  //       max_v_point = i; // 坐标值
  //     }
  //   }
  // }  
  // s_sy = max_v_point - max_v_val; // 开始坐标(y)
  // s_height = max_v_val;

  rect_list[index].s_sx = s_sx;
  rect_list[index].s_sy = s_sy;
  rect_list[index].Rect_width = s_width;
  rect_list[index].Rect_height = s_height;

  //更新判断条件
  // max_h = max_v_val;
  // max_w = max_h_val;


  //释放空间，节省内存
  // memset(h_integ, NULL, w*h*sizeof(uint16_t));  //将h_integ指向的内存空间置为空
  free (h_integ); //释放空间
  // memset(v_integ, NULL, w*h*sizeof(uint16_t));  //将v_integ指向的内存空间置为空
  free(v_integ); //释放空间

  free(out_put_mask);//释放内存
  //返回包含结构体的数组
  return rect_list;
}
