# app.py
import logging, time
from flask import Flask, request, jsonify
from akuvox import set_zone_status, open_door

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("webhook")

ZONE = 8


@app.route("/down", methods=["GET"])
def down():
    time.sleep(5)
    ip = request.remote_addr
    log.info(f"→ /down ПРИШЁЛ от {ip}")
    result = set_zone_status(ip, ZONE, status=0)
    log.info(f"← /down ответ: {result}")
    return jsonify(result), (200 if result["ok"] else 502)


@app.route("/up", methods=["GET"])
def up():
    ip = request.remote_addr
    log.info(f"→ /up ПРИШЁЛ от {ip}")

    log.info(f"→ /up открываю дверь")
    door = open_door(ip)
    log.info(f"← /up дверь: {door}")

    log.info(f"→ /up пауза 10 мс")
   # time.sleep(0.010)

    log.info(f"→ /up ставлю зону {ZONE} в 24H")
    result = set_zone_status(ip, ZONE, status=2)
    log.info(f"← /up зона: {result}")

    ok = door["ok"] and result["ok"]
    log.info(f"← /up ответ: ok={ok}")
    return jsonify({"door": door, "zone": result}), (200 if ok else 502)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1000, debug=True)