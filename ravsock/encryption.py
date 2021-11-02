import os

import tenseal as ts

# from .config import BASE_DIR
from tenseal.enc_context import SecretKey

BASE_DIR = ""


def get_context():
    # Setup TenSEAL context
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )

    context.generate_galois_keys()
    context.global_scale = 2 ** 40
    return context


def dump_context(context, filepath, save_secret_key=False):
    with open(filepath, "wb") as f:
        f.write(context.serialize(save_secret_key=save_secret_key))


def load_context(file_path):
    with open(file_path, "rb") as f:
        return ts.context_from(f.read())


# if __name__ == '__main__':
#     context, key = get_context()
#
#     key.data.save("key.txt")
#     sc = context.secret_key().data.load(context, "key.txt")
#     print(sc)
#
#     exit()
#
#     with open("key.txt", "rb") as f:
#         print(SecretKey(data=None).data.load(f.read()))
#
#     print(key)
#
#     key = SecretKey(data=key.data)
#
#     import pickle
#
#     with open("key.pkl", "w") as f:
#         pickle.dump(key.data.save("a.txt"), f, protocol=pickle.HIGHEST_PROTOCOL)
