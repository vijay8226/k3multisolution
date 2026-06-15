import random

def generate_otp():
    return str(random.randint(1000, 9999))  # 4-digit OTP


def send_otp(mobile, otp_code):
    # SIMULATED - prints OTP to terminal instead of sending real SMS
    print(f"\n{'='*40}")
    print(f"OTP for {mobile}: {otp_code}")
    print(f"{'='*40}\n")
    # Later, replace this with real SMS API call (e.g., Fast2SMS, Twilio)