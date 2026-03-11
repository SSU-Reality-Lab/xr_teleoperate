#!/bin/bash
# G1 EDU + Quest 3 Teleoperation Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TELEOP_DIR="$SCRIPT_DIR/teleop"

# Activate conda environment
if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
    echo "ERROR: conda not found in miniconda3 or anaconda3"
    exit 1
fi
conda activate tv

# Mode selection
echo "========================================"
echo "  G1_29 + Dex3 Teleoperation Launcher"
echo "========================================"
echo ""
echo "  1) Waist follow + Pass-through"
echo "  2) Waist follow + Ego (waist-max-deg=180)"
echo "  3) Upper body only + Ego (no motion)"
echo "  4) Waist follow + Ego (custom waist-max-deg)"
echo "  5) Simulation + Ego (waist-max-deg=180)"
echo ""
read -p "Select mode [1-5]: " MODE_SELECT

DISPLAY_MODE=""
WAIST_OPTS=""
MOTION_OPT="--motion"
SIM_OPT=""

case $MODE_SELECT in
    1)
        DISPLAY_MODE="pass-through"
        WAIST_OPTS="--waist-follow"
        ;;
    2)
        DISPLAY_MODE="ego"
        WAIST_OPTS="--waist-follow --waist-max-deg 180"
        ;;
    3)
        DISPLAY_MODE="ego"
        WAIST_OPTS=""
        MOTION_OPT=""
        ;;
    4)
        DISPLAY_MODE="ego"
        read -p "Enter waist-max-deg [default: 35]: " WAIST_DEG
        WAIST_DEG=${WAIST_DEG:-35}
        WAIST_OPTS="--waist-follow --waist-max-deg $WAIST_DEG"
        ;;
    5)
        DISPLAY_MODE="ego"
        WAIST_OPTS="--waist-follow --waist-max-deg 180"
        MOTION_OPT=""
        SIM_OPT="--sim"
        ;;
    *)
        echo "Invalid selection. Exiting."
        exit 1
        ;;
esac

# Check network connectivity to G1 robot (skip in sim mode)
if [[ -z "$SIM_OPT" ]]; then
    echo "Checking G1 robot network (192.168.123.x)..."
    if ping -c 1 -W 2 192.168.123.161 > /dev/null 2>&1; then
        echo "G1 robot reachable at 192.168.123.161"
    else
        echo "WARNING: Cannot reach G1 robot at 192.168.123.161"
        echo "Make sure ethernet is connected and IP is configured (192.168.123.2)"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi
fi

# Check SSL certificates
if [[ ! -f "$HOME/.config/xr_teleoperate/cert.pem" ]]; then
    echo "ERROR: SSL certificate not found at ~/.config/xr_teleoperate/cert.pem"
    exit 1
fi

echo ""
echo "Controls:"
echo "  r - Start teleoperation"
echo "  s - Start/stop episode recording"
echo "  arrow keys - Soft E-stop (damping mode)"
echo "  q - Quit"
echo ""

cd "$TELEOP_DIR"

RECORD_DIR="/data/G1"
python teleop_hand_and_arm.py --arm=G1_29 --ee=dex3 \
    --display-mode $DISPLAY_MODE --input-mode hand \
    $MOTION_OPT $WAIST_OPTS --waist-gain 1.0 \
    $SIM_OPT \
    --record --task-dir "$RECORD_DIR" --task-name "teleop" \
    "$@"

# --display-mode 옵션:
#   immersive    : Quest 3에 로봇 카메라 영상을 송출 (기본값)
#   pass-through : 영상 송출 없이 Quest 3 패스스루(현실 배경)만 표시. 핸드 트래킹은 정상 동작
#   ego          : 1인칭 시점 모드
# --motion: 하체 밸런스 모드를 유지 (없으면 Enter_Debug_Mode가 하체 힘을 빼버림)
# --waist-follow: 허리 yaw가 VR 사용자의 몸 회전을 따라감 (실험적)
#   관련 옵션: --waist-gain 1.0 --waist-max-deg 35 --waist-smoothing 0.15 --waist-deadband-deg 3
# --record: 데이터 녹화 활성화
# --task-dir: 녹화 데이터 저장 경로
# --task-name: 태스크 이름 (task-dir 아래 하위 폴더명)
