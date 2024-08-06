ARG PARENT_VERSION=latest
FROM p4lang/p4c:${PARENT_VERSION}
LABEL maintainer="P4 Developers <p4-dev@lists.p4.org>"

COPY . /openoptics-mininet/
WORKDIR /openoptics-mininet/

RUN apt-get update -qq && \
    apt-get install -qq --no-install-recommends \
    wget \
    python3-pip \
    git \
    nano \
    mininet \
    make \
    g++ \
    autoconf \
    lsb-release \
    iputils-ping \
    ssh \
    redis-server \
    ethtool

RUN pip3 install networkx matplotlib mininet asgiref channels-redis Django nnpy daphne

RUN rm -rf /usr/local/bin/thrift /usr/local/include/thrift /usr/local/include/bm/ /usr/local/bin/bm_CLI /usr/local/bin/bm_nanomsg_events /usr/local/bin/bm_p4dbg  

RUN git clone https://github.com/p4lang/behavioral-model.git
WORKDIR behavioral-model
RUN git checkout 8e183a39b372cb9dc563e9d0cf593323249cd88b
RUN cp -r ../targets/tor_switch ./targets
RUN cp -r ../targets/optical_switch ./targets
RUN cp ../targets/configure.ac ./configure.ac
RUN cp ../targets/Makefile.am ./targets

ENV BM_DEPS automake \
            build-essential \
            clang-8 \
            clang-10 \
            curl \
            git \
            lcov \
            libgmp-dev \
            libpcap-dev \
            libboost-dev \
            libboost-program-options-dev \
            libboost-system-dev \
            libboost-filesystem-dev \
            libboost-thread-dev \
            libtool \
            pkg-config
ENV BM_RUNTIME_DEPS libboost-program-options1.71.0 \
                    libboost-system1.71.0 \
                    libboost-filesystem1.71.0 \
                    libboost-thread1.71.0 \
                    libgmp10 \
                    libpcap0.8 \
                    python3 \
                    python-is-python3
RUN apt-get update -qq && apt-get install -qq --no-install-recommends $BM_DEPS $BM_RUNTIME_DEPS

WORKDIR ..
RUN wget https://dlcdn.apache.org/thrift/0.20.0/thrift-0.20.0.tar.gz
RUN tar -xvf thrift-0.20.0.tar.gz
WORKDIR thrift-0.20.0
RUN ./configure
RUN make -j$(nproc)
RUN make install

RUN ldconfig

WORKDIR ../behavioral-model
RUN ./autogen.sh
RUN ./configure 'CXXFLAGS=-O0 -g' --enable-debugger
RUN make -j$(nproc)
RUN make install

RUN service redis-server start

EXPOSE 5201/tcp 5201/udp
EXPOSE 5001/tcp 5001/udp

WORKDIR ..