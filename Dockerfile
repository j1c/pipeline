# Use nvidia docker image for cuda
FROM nvidia/cuda:9.1-devel-ubuntu16.04

# Pre-cache neurodebian key
COPY neurodebian.gpg /neurodebian.gpg

# Core system capabilities required
RUN apt-get update && apt-get install -y \
    bc \
    build-essential \
    curl \
    dc \
    git \
    libegl1-mesa-dev \
    libopenblas-dev \
    liblapack-dev \
    nano \
    python2.7 \
    tar \
    tcsh \
    unzip \
    wget

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get install -y tzdata

# PPA for newer version of nodejs, which is required for bids-validator
RUN curl -sL https://deb.nodesource.com/setup_12.x -o nodesource_setup.sh && \
    bash nodesource_setup.sh && \
    rm -f nodesource_setup.sh
RUN apt-get install -y nodejs

# NeuroDebian setup
RUN wget -qO- http://neuro.debian.net/lists/xenial.us-ca.full | \
    tee /etc/apt/sources.list.d/neurodebian.sources.list
RUN apt-key add /neurodebian.gpg && \
    apt-get update

# Install ANTS 2.2.0
RUN apt-get install -y ants

# Make ANTS happy
ENV ANTSPATH /usr/lib/ants
ENV PATH /usr/lib/ants:$PATH

# #---------AFNI INSTALL--------------------------------------------------------#
# # setup of AFNI, which provides robust modifications of many of neuroimaging
# # algorithms
RUN apt-get update -qq && apt-get install -yq --no-install-recommends ed gsl-bin libglu1-mesa-dev libglib2.0-0 libglw1-mesa fsl-atlases \
    libgomp1 libjpeg62 libxm4 netpbm tcsh xfonts-base xvfb && \
    libs_path=/usr/lib/x86_64-linux-gnu && \
    if [ -f $libs_path/libgsl.so.19 ]; then \
    ln $libs_path/libgsl.so.19 $libs_path/libgsl.so.0; \
    fi

RUN mkdir -p /opt/afni && \
    curl -o afni.tar.gz -sSLO "$AFNI_URL" && \
    tar zxv -C /opt/afni --strip-components=1 -f afni.tar.gz && \
    rm -rf afni.tar.gz
ENV PATH=/opt/afni:$PATH

# FSL installer appears to now be ready for use with version 6.0.0
# eddy is also now included in FSL6
RUN wget -q http://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
    chmod 775 fslinstaller.py
RUN python2 /fslinstaller.py -d /opt/fsl -V 6.0.4 -q
RUN rm -f /fslinstaller.py
RUN which immv || ( rm -rf /opt/fsl/fslpython && /opt/fsl/etc/fslconf/fslpython_install.sh -f /opt/fsl || ( cat /tmp/fslpython*/fslpython_miniconda_installer.log && exit 1 ) )

# Make FSL happy
ENV FSLDIR /opt/fsl
ENV PATH $FSLDIR/bin:$PATH
RUN /bin/bash -c 'source /opt/fsl/etc/fslconf/fsl.sh'
ENV FSLOUTPUTTYPE="NIFTI_GZ"

# apt cleanup to recover as much space as possible
RUN apt-get remove -y libegl1-mesa-dev && apt-get autoremove -y
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh && \
    bash Miniconda3-4.5.11-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.5.11-Linux-x86_64.sh

# Set CPATH for packages relying on compiled libs (e.g. indexed_gzip)
ENV PATH="/usr/local/miniconda/bin:$PATH" \
    CPATH="/usr/local/miniconda/include/:$CPATH" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1

RUN conda install -y python=3.7.1 \
    pip=19.1

# Precaching fonts, set 'Agg' as default backend for matplotlib
RUN python -c "from matplotlib import font_manager" \
    && sed -i 's/\(backend *: \).*$/\1Agg/g' $( python -c "import matplotlib; print(matplotlib.matplotlib_fname())" ) \
    #&& pip install --upgrade pip \
    #&& apt-get update && apt-get install -y sudo gfortran liblapack-dev libopenblas-dev \
    && pip install ipython cython parse \
    && git clone -b homecooked https://github.com/j1c/dmriprep.git dmriprep \
    && cd dmriprep \
    && python setup.py install

ENV IS_DOCKER_8395080871=1

RUN ldconfig
WORKDIR /tmp/
ENTRYPOINT ["/usr/local/miniconda/bin/dmriprep"]