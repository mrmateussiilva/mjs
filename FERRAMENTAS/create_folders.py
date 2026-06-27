
import os
from os.path import exists,join


def create_folders(path_base:str, name_folders:list[str]) -> bool | Exception:
    for folder in name_folders:
        p = join(path_base,folder)
        if exists(p):
            continue
        try:
            os.mkdir(p)
        except Exception as e:
            print(e)
    return True


def main():
    PATH = r"Z:\26 06 2026"
    NAMES_FOLDERS = [
    r"BOLSINHAS",
    r"BOLSINHAS\PARA FAZER",
    r"PAINEL_CUT",
    r"CONF",
    r"APS",
    r"TEX",
    ]
    create_folders(path_base=PATH,name_folders=NAMES_FOLDERS)


if __name__ == "__main__":
    main()
