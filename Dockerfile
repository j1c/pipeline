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
ENV AFNI_URL https://files.osf.io/v1/resources/fvuh8/providers/osfstorage/5a0dd9a7b83f69027512a12b

RUN apt-get update -qq && apt-get install -yq --no-install-recommends ed gsl-bin libglib2.0-0 libglw1-mesa fsl-atlases \
    libgomp1 libjpeg62 libxm4 netpbm xfonts-base xvfb && \
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
RUN rm -rf /opt/fsl/data \
    && rm -rf /opt/fsl/bin/FSLeyes* \
    && rm -rf /opt/fsl/src \
    && rm -rf /opt/fsl/extras/src \
    && rm -rf /opt/fsl/doc \
    && rm -rf /opt/fsl/bin/fslview.app \
    && rm -rf /opt/fsl/data/atlases \
    && rm -rf /opt/fsl/data/first \
    && rm -rf /opt/fsl/data/mist \
    && rm -rf /opt/fsl/data/possum
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

# Install conda
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh && \
    bash Miniconda3-4.5.11-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.5.11-Linux-x86_64.sh

# Set CPATH for packages relying on compiled libs (e.g. indexed_gzip)
ENV PATH="/usr/local/miniconda/bin:$PATH" \
    CPATH="/usr/local/miniconda/include/:$CPATH" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1

RUN conda install -y python=3.7.* \
    pip \
    matplotlib=2.2.2

# Precaching fonts, set 'Agg' as default backend for matplotlib
RUN python -c "from matplotlib import font_manager" \
    && sed -i 's/\(backend *: \).*$/\1Agg/g' $( python -c "import matplotlib; print(matplotlib.matplotlib_fname())" )
#&& pip install ipython \

RUN git clone -b homecooked https://github.com/j1c/dmriprep.git dmriprep \
    && cd dmriprep \
    && python setup.py install 

RUN git clone -b bug_fix https://github.com/j1c/m2g.git m2g \
    && cd ../m2g \ 
    && pip install -r requirements.txt \
    && pip install .

RUN git clone https://github.com/j1c/hcp2bids \
    && cd ../hcp2bids \
    && pip install .

RUN git clone https://github.com/neurodata/hcp_pipelines \
    && cd ../hcp_pipelines \ 
    && pip install .

RUN ldconfig
WORKDIR /tmp/
ENTRYPOINT ["/usr/local/miniconda/bin/"]