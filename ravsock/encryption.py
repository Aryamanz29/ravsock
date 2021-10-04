import tenseal as ts

# Setup TenSEAL context
context = ts.context(
    ts.SCHEME_TYPE.CKKS,
    poly_modulus_degree=8192,
    coeff_mod_bit_sizes=[60, 40, 40, 60]
)

context.public_key()

context.generate_galois_keys()
context.global_scale = 2 ** 40
secret_key = context.secret_key()
context.make_context_public()


