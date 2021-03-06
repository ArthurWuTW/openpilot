from cereal import car
from cereal import log

VisualAlert = car.CarControl.HUDControl.VisualAlert
AudibleAlert = car.CarControl.HUDControl.AudibleAlert

def calc_checksum(data):
  """This function does not want the checksum byte in the input data.

  jeep chrysler canbus checksum from http://illmatics.com/Remote%20Car%20Hacking.pdf
  """
  end_index = len(data)
  index = 0
  checksum = 0xFF
  temp_chk = 0;
  bit_sum = 0;
  if(end_index <= index):
    return False
  for index in range(0, end_index):
    shift = 0x80
    curr = data[index]
    iterate = 8
    while(iterate > 0):
      iterate -= 1
      bit_sum = curr & shift;
      temp_chk = checksum & 0x80
      if (bit_sum != 0):
        bit_sum = 0x1C
        if (temp_chk != 0):
          bit_sum = 1
        checksum = checksum << 1
        temp_chk = checksum | 1
        bit_sum ^= temp_chk
      else:
        if (temp_chk != 0):
          bit_sum = 0x1D
        checksum = checksum << 1
        bit_sum ^= checksum
      checksum = bit_sum
      shift = shift >> 1
  return ~checksum & 0xFF


def make_can_msg(addr, dat):
  return [addr, 0, dat, 0]


def create_lkas_hud(packer, gear, lkas_active, hud_alert, hud_count, lkas_car_model):
  # LKAS_HUD 0x2a6 (678) Controls what lane-keeping icon is displayed.

  if hud_alert == VisualAlert.steerRequired:
    msg = '0000000300000000'.decode('hex')
    return make_can_msg(0x2a6, msg)

  color = 1  # default values are for park or neutral in 2017 are 0 0, but trying 1 1 for 2019
  lines = 1
  alerts = 0

  if hud_count < (1 *4):  # first 3 seconds, 4Hz
    alerts = 1
  # CAR.PACIFICA_2018_HYBRID and CAR.PACIFICA_2019_HYBRID
  # had color = 1 and lines = 1 but trying 2017 hybrid style for now.
  if gear in ('drive', 'reverse', 'low'):
    if lkas_active:
      color = 2  # control active, display green.
      lines = 6
    else:
      color = 1  # control off, display white.
      lines = 1

  values = {
    "LKAS_ICON_COLOR": color,  # byte 0, last 2 bits
    "CAR_MODEL": lkas_car_model,  # byte 1
    "LKAS_LANE_LINES": lines,  # byte 2, last 4 bits
    "LKAS_ALERTS": alerts,  # byte 3, last 4 bits
    }

  return packer.make_can_msg("LKAS_HUD", 0, values)  # 0x2a6


def create_lkas_command(packer, apply_steer, moving_fast, frame):
  # LKAS_COMMAND 0x292 (658) Lane-keeping signal to turn the wheel.
  values = {
    "LKAS_STEERING_TORQUE": apply_steer,
    "LKAS_HIGH_TORQUE": int(moving_fast),
    "COUNTER": frame % 0x10,
  }

  dat = packer.make_can_msg("LKAS_COMMAND", 0, values)[2]
  dat = [ord(i) for i in dat][:-1]
  checksum = calc_checksum(dat)

  values["CHECKSUM"] = checksum
  return packer.make_can_msg("LKAS_COMMAND", 0, values)


def create_chimes(audible_alert):
  # '0050' nothing, chime '4f55'
  if audible_alert == AudibleAlert.none:
    msg = '0050'.decode('hex')
  else:
    msg = '4f55'.decode('hex')
  return make_can_msg(0x339, msg)


def create_wheel_buttons(frame):
  # WHEEL_BUTTONS (571) Message sent to cancel ACC.
  start = [0x01]  # acc cancel set
  counter = (frame % 10) << 4
  dat = start + [counter]
  dat = dat + [calc_checksum(dat)]
  return make_can_msg(0x23b, str(bytearray(dat)))


def create_openpilot_path_poly_front(packer, frame, Poly, Prob, CanName):
  #print lanePoly.pathPlan.lPoly[3]
  values = {
    "PROB": int(Prob*10),
    "THIRD_ORDER_SIGN": int(bool(Poly[0]>0)),
    "THIRD_ORDER": int(abs(int(Poly[0]*100000000))),  #third order *10^8
    "SECOND_ORDER_SIGN": int(bool(Poly[1]>0)),
    "SECOND_ORDER": int(abs(int(Poly[1]*1000000))),  # 10^6
    "COUNTER": int(frame % 256)
  }
  #print values

  return packer.make_can_msg(CanName, 0, values)

def create_openpilot_path_poly_back(packer, frame, Poly, Prob, CanName):
  #print lanePoly.pathPlan.lPoly[3]
  values = {
    "FIRST_ORDER_SIGN": int(bool(Poly[2]>0)),
    "FIRST_ORDER": int(abs(int(Poly[2]*1000000))),    # 10^6
    "ZERO_ORDER_SIGN": int(bool(Poly[3]>0)),
    "ZERO_ORDER": int(abs(int(Poly[3]*1000000))),     # 10^6
    "COUNTER": int(frame % 256)
  }
  #print values

  return packer.make_can_msg(CanName, 0, values)

def create_openpilot_steering_angle(packer, frame, actuators, CanName):
  values = {
    "STEERING_ANGLE": int(abs(actuators.steer * 10000)),
    "STEERING_ANGLE_SIGN": int(bool(actuators.steer>0)),
    "STEERING_ANGLE_TARGET": int(abs(actuators.steerAngle * 10000)),
    "STEERING_ANGLE_TARGET_SIGN": int(bool(actuators.steerAngle>0)),
    "COUNTER": int(frame % 256)
  }
  #print values
  return packer.make_can_msg(CanName, 0, values)
