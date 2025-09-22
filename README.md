# SONY-DUT-SSUP
## Arm Control

We use the SONY Spresense board to transmit positional coordinate signals to a robotic arm. The robotic arm can then adjust its orientation based on these signals to accurately identify and grasp objects. This setup ensures precise object location recognition and efficient handling.

## Avoidance Control

We utilize the SONY Spresense board connected to an external ToF (Time-of-Flight) depth camera to acquire real-time depth information. This setup enables obstacle avoidance functionality, with the SONY Spresense board playing a crucial role in processing and transmitting the depth data to ensure smooth and efficient navigation.

## Path Control

Using the SONY Spresense board with its companion camera, we have developed a color tracking model trained on SONY's NNC (Neural Network Console) platform. The SONY Spresense board then controls a mobile vehicle, enabling precise path control and navigation based on the color tracking algorithm.

## Positioning Control

Using the SONY Spresense board paired with a ToF (Time-of-Flight) camera, we have achieved precise position control for a mobile vehicle. This system ensures the vehicle can accurately stop at designated locations by utilizing real-time depth information processed by the SONY Spresense board.

## Target Tracking

Using the SONY Spresense board and a tracking algorithm trained on SONY's NNC (Neural Network Console) platform, we have enabled a following vehicle to track a leading vehicle in real-time. Both vehicles are controlled by SONY Spresense boards, ensuring precise and coordinated movement.

## Playdrum

Using the SONY Mocopi QM-SS1 portable motion capture sensor to simulate basic drum kit,  you can simulate the sounds of various drum components by moving the sensors. The code implements four types of performance modes: basic performance implementation; performance of specified scores; optimization of performance by the model and generative performance by the model.If you want to run the code, you need to place the DrumSamples local path in the correct location in the code and configure drumEnv.yml in the Anaconda environment. The optimized model and the automatically generated model have been included in the file.

## Playguitar

Using the SONY Spresense board, a Jetson Orin NX Developer Kit, a Bluetooth keyboard and a depth sensor, you can simulate playing the guitar.The code implements four types of performance modes: basic performance implementation; performance of specified scores; optimization of performance by the model and generative performance by the model.If you want to run the code, you need to place the GuitarSamples local path in the correct location in the code and configure guitarEnv.yml in the Anaconda environment. Most importantly, due to the upload restrictions, there are no optimized model and automatically generated model in this file. Please contact my email if you need them.
                                                                                                                                                                                                         email:stone.shi911@gmail.com

