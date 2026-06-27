import pickle
import os
from os.path import join, isfile


list_models = [
    filee
    for filee in os.listdir(".") 
    if isfile(filee) and not  str(filee).endswith(".py")
]

def read_model(path_model) -> str|None:
    with open(path_model,"rb") as f:
        data = pickle.load(f)
    return data


import time 
if __name__ == "__main__":
    for model in list_models:
        # print((model))

        print(read_model(model))
        time.sleep(10)
        print("-----------------Outro modelo----------------------\n")
# # Open the file in read-binary mode ('rb')
# with open('your_file.pkl', 'rb') as file:
#     data = pickle.load(file)

# # View the contents
# print(data)