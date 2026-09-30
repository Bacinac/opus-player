FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# The transcoder is Jellyfin's ffmpeg build and Intel's compute runtime — his
# engine, not his product, which is exactly the split this module was asked for.
#
# Debian's own ffmpeg has the VAAPI encoders but its tone-mapping is broken on
# this card: tonemap_vaapi crushes an HDR picture to near-black (732 KB for forty
# seconds of 1080p). Jellyfin's build plus the OpenCL runtime does it properly at
# 6.3x realtime. The compute runtime is not in Debian, so it comes from Intel's
# own releases the same way Jellyfin's image gets it.
ARG IGC=https://github.com/intel/intel-graphics-compiler/releases/download/v2.38.2
ARG NEO=https://github.com/intel/compute-runtime/releases/download/26.27.39122.11
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates ocl-icd-libopencl1 \
    && install -d /etc/apt/keyrings \
    && curl -fsSL https://repo.jellyfin.org/jellyfin_team.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/jellyfin.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/jellyfin.gpg] https://repo.jellyfin.org/debian trixie main" \
        > /etc/apt/sources.list.d/jellyfin.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends jellyfin-ffmpeg7 \
    && cd /tmp \
    && curl -fsSLO ${IGC}/intel-igc-core-2_2.38.2+22051_amd64.deb \
    && curl -fsSLO ${IGC}/intel-igc-opencl-2_2.38.2+22051_amd64.deb \
    && curl -fsSLO ${NEO}/intel-opencl-icd_26.27.39122.11-0_amd64.deb \
    && curl -fsSLO ${NEO}/libigdgmm12_22.10.0_amd64.deb \
    && dpkg -i /tmp/*.deb \
    && rm -f /tmp/*.deb \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY requirements.lock ./
RUN uv pip install --system --require-hashes -r requirements.lock
RUN --mount=type=bind,from=plugins,target=/plugins \
    for lock in /plugins/*/requirements/opus-player.lock; do \
        [ ! -f "$lock" ] || uv pip install --system --require-hashes -r "$lock"; \
    done

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1

CMD ["./entrypoint.sh"]
