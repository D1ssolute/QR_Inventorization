from pioneer_sdk import Pioneer, Camera
from more_itertools import locate
import cv2
import numpy as np
import time

"""Предполагается, что склад в рамках кейса состоит из одной площадки в которой находится 2 ряда полок по 3 предмета
в каждой (подробнее в инструкции). Некоторые предметы могут отсутствовать, но дрон всё равно попытается их найти.
Площадка определяется следующими параметрами:"""
storage_height = 2
storage_width = 3
x_inc = float(0.5)  # расстояние между соседними предметами в одном ряду
z_inc = float(0.5)  # расстояние между рядами
start_height = float(1.5)  # высота верхней полки


def inventorize(drone, camera_ip):
    """
    Функция инвентаризации. Дрон пролетает ряд за рядом, начиная с крайней верхней левой точки складского стеллажа и
    пытается отсканировать QR-код в каждой ячейке в течении 2.5 секунд, занося её содержимое в два массива:
    массив имён и массив количеств содержащихся предметов. После инвентаризации возвращается на изначальную позицию и
    садится.
    :param drone: экземпляр класса Pioneer
    :param camera_ip: экземпляр класса Camera
    :return storage_name, storage_quantity: массив имён и массив количеств содержащихся на стеллаже предметов
    """
    storage_name = []  # массив для сохранения имён хранящихся предметов
    storage_quantity = []  # массив для сохранения кол-ва хранящихся предметов
    counter = 1
    command_x = float(0)
    command_z = float(start_height)
    detector = cv2.QRCodeDetector()  # инициализация детектора для сканирования QR-кодов
    new_point = True
    while True:
        try:
            camera_frame = camera_ip.get_cv_frame()  # получение кадра с камеры
            if np.sum(camera_frame) == 0:  # если кадр не получен, начинает новую итерацию
                continue
            cv2.imshow('QR Reading', camera_frame)  # вывод изображения на экран

            if new_point:  # если дрон просканировал ячейку, двигается к следующей ячейке
                new_point = False
                drone.go_to_local_point(x=command_x, y=0, z=command_z, yaw=0)

            if drone.point_reached():  # если новая точка достигнута
                timer = time.time()  # записывает время до начала сканирования
                # В цикле дрон пытается найти и просканировать QR-код. Если он его не нашёл в течении 2.5 секунд, то
                # предполагается, что предмета нет. Во время цикла дрон игнорирует нажатие esc и не выводит картинку.
                while True:
                    try:
                        gray = cv2.cvtColor(camera_ip.get_cv_frame(), cv2.COLOR_BGR2GRAY)  # обесцвечивание кадра
                        string, _, _ = detector.detectAndDecode(gray)  # попытка извлечь строку из QR-кода
                        if string is not None or (time.time() - timer > float(2.5)):
                            break
                    except:
                        continue

                if string is not None:  # если QR-код найден
                    text = string.split()  # разбиение строки на массив из отдельных элементов, разделённых пробелом
                    print("[INFO] Найден предмет", text[0], "в количестве", text[1])
                    storage_name.append(text[0])  # записываем имя в массив имён
                    storage_quantity.append(int(text[1]))  # записываем кол-во в численном формате в массив кол-в
                else:
                    print("[INFO] На данной полке предмет отсутствует")
                    # в случае отсутствия предмета на полке, запишем в массивы следующие значения:
                    storage_name.append("None")
                    storage_quantity.append(int(0))

                if counter == storage_height * storage_width:  # если ячейка последняя
                    print("[INFO] Инвентаризация завершена:")
                    print(storage_name)
                    print(storage_quantity)
                    # возвращаемся на начальную точку и садимся, перед тем как опрашивать пользователя
                    drone.go_to_local_point(x=0, y=0, z=command_z, yaw=0)
                    while True:
                        if drone.point_reached():
                            drone.land()
                            return storage_name, storage_quantity
                elif counter == storage_width:  # если ячейка последняя в ряду - переход на новый ряд
                    command_x = float(0)
                    command_z -= z_inc
                else:
                    command_x += x_inc
                new_point = True
                counter += 1
        except cv2.error:
            continue

        key_ip = cv2.waitKey(1)  # проверяем нажатие клавиши esc для предварительного завершения программы
        if key_ip == 27:
            print('[INFO] ESC нажат, программа завершается')
            drone.land()
            time.sleep(5)
            cv2.destroyAllWindows()
            exit()


def find_item(result, drone):
    """
    Функция нахождения и подсвечивания предмета. Рассчитывает, на какое расстояние дрону нужно переместиться, чтобы
    достигнуть нужной ячейки.
    :param result: индекс ячейки с необходимым предметом
    :param drone: экземпляр класса Pioneer
    """
    drone.arm()
    drone.takeoff()
    col = result
    row = 0
    # т.к. номера ячеек проставляются друг за другом, с помощью цикла нужно определить конкретный ряд, где находится
    # данная ячейка, а так же её *столбец*
    for j in range(storage_height-1):
        if col < storage_width:
            row = j
            break
        else:
            col -= storage_width
    cmd_x = float(x_inc*col)  # определяем расстояние до столбца с предметом
    cmd_z = start_height-float(z_inc*row)  # определяем высоту нужного ряда
    drone.go_to_local_point(x=cmd_x, y=0, z=cmd_z, yaw=0)
    while True:
        if drone.point_reached():
            break
    print("Дрон подсвечивает ячейку")
    drone.led_control(r=0, g=255, b=0)
    time.sleep(3)
    drone.led_control(r=0, g=0, b=0)


if __name__ == '__main__':
    pioneer_mini = Pioneer()  # pioneer_mini как экземпляр класса Pioneer
    pioneer_mini.arm()
    pioneer_mini.takeoff()
    camera = Camera()  # camera как экземпляр класса Camera

    names, quantities = inventorize(pioneer_mini, camera)

    item_found = False
    while True:
        item = input("Какой предмет нужно найти? ")
        if item == "exit":  # команда exit позволит закрыть запрос и завершить программу предварительно
            print("[INFO] Программа завершается предварительно")
            cv2.destroyAllWindows()  # закрывает окно с выводом изображения
            exit(0)
        if item in names:  # если запрошенный предмет находится в массиве имён (т.е. на складе)
            quantity = int(input("В каком количестве? "))
            indexes = list(locate(names, lambda x: x == item))  # находим все ячейки, где встречается этот предмет
            # проверяем, соответствует ли запрошенное кол-во числу предметов в каждой отдельной ячейке
            for i in range(len(indexes)):
                if quantity <= quantities[indexes[i]]:
                    result_index = indexes[i]  # номер ячейки
                    item_found = True  # флаг, чтобы выйти из внешнего цикла
                    print("Ячейка", result_index + 1, "содержит", item, "в нужном количестве")
                    break
            if item_found:
                break
            print(item, "в нужном количестве не найден, повторите попытку")
        else:
            print("Такого предмета нет на складе, повторите попытку")

    find_item(result_index, pioneer_mini)

    pioneer_mini.land()
    time.sleep(5)
    cv2.destroyAllWindows()  # закрывает окно с выводом изображения
    exit(0)
