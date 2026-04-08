import requests
import cv2 
import os
base_url = "http://localhost:8080"

def taking_off(alt=10):
    params = {"alt": alt}
    takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
    if takeoff_result.status_code != 200:
        print(f"Take off command fail. status_code={takeoff_result.status_code}")
        exit()
    print("Vehicle took off")

def arming_vehicle():
    arm_result = requests.get(f"{base_url}/command/arm")
    if arm_result.status_code != 200:
        print(f"Arm command fail. status_code={arm_result.status_code}")
        exit()
    print("Vehicle armed.")

def landing():
    land_result = requests.get(f"{base_url}/command/land")
    if land_result.status_code != 200:
        print(f"Land command fail. status_code={land_result.status_code}")
        exit()
    print("Vehicle landed.")

def drive_wait(move):
    move_data = {
        "x": move[0],
        "y": move[1],
        "z": move[2]
    }
    move_result = requests.post(
        f"{base_url}/movement/drive_wait",
        json=move_data
    )

    if move_result.status_code != 200:
        print(
            f"Drive_wait command fail. "
            f"status_code={move_result.status_code} move={move}"
        )
        exit()

    print(f"Vehicle moved {move}")


def take_picture(device):
    output = "img.jpg"
        
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)

    if not cap.isOpened():
        print("Erro ao abrir a câmera")
        exit(1)

    ret, frame = cap.read()

    if not ret:
        print("Erro ao capturar imagem")
    else:
        cv2.imwrite(output, frame)
        #print("Foto salva em", output)

    cap.release()

def read_qrcode():
    detector = cv2.QRCodeDetector()

    img = cv2.imread("img.jpg")
    if img is None:
        print("Erro ao abrir a imagem")
        return None

    data, bbox, _ = detector.detectAndDecode(img)

    if data:
        print("QR Code lido:", data)
        return data

    print("Nenhum QR detectado")
    return None

def uav_commands(data):
    if data == "takeoff_&_landing":
        arming_vehicle()
        taking_off()
        landing()
    elif data =="make_a_square":
       pass
    elif data=="push_force":
        drive_wait([1,0,0])
    elif data == "right":
        drive_wait([0,1,0])
    elif data == "left":
        drive_wait([0,-1,0])
    elif data == "takeoff":
        arming_vehicle()
        taking_off(alt=1)
    elif data == "landing":
        landing()

def delete_img():
    os.remove("img.jpg")



def main():
    
    while 1:
        take_picture(device="/dev/video2")
        data = read_qrcode()
        delete_img()
        uav_commands(data=data)
        


main()