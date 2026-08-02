from config import Config


def get_avaiable_keys():
    return [{k: v} for k, v in vars(Config).items() if not k.startswith("_")]
