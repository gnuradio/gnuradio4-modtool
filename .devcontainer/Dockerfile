# Development container for gr4_modtool itself.
# Base image includes gcc, clang, cmake, ninja, git, and a non-root 'vscode' user.
FROM mcr.microsoft.com/devcontainers/cpp:ubuntu26.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    clang-format \
    clang-tidy \
    libfmt-dev \
    libcpp-httplib-dev \
    python3-pip \
    python3-venv \
    pipx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# boost-ut (header-only) — needed to compile generated OOT block tests in e2e runs
RUN mkdir -p /usr/local/include/boost && curl -fsSL \
    https://raw.githubusercontent.com/boost-ext/ut/master/include/boost/ut.hpp \
    -o /usr/local/include/boost/ut.hpp

# ── GNURadio 4 ────────────────────────────────────────────────────────────────
# Built from source so the e2e tests (tests/e2e/), which compile and run
# generated OOT blocks against an installed gnuradio4, work out of the box.
RUN git clone --depth 1 https://github.com/gnuradio/gnuradio4.git /opt/gnuradio4 \
    && cmake -S /opt/gnuradio4 -B /opt/gnuradio4/build \
             -DCMAKE_INSTALL_PREFIX=/usr/local \
             -DENABLE_TESTING=OFF \
             -DENABLE_EXAMPLES=OFF \
    && cmake --build /opt/gnuradio4/build --parallel "$(nproc)" \
    && cmake --install /opt/gnuradio4/build \
    && rm -rf /opt/gnuradio4
