import qrcode
data = "right"
img = qrcode.make(data)

type(img)  # qrcode.image.pil.PilImage
img.save(f"./qrcodes/qr_code_{data}.png")