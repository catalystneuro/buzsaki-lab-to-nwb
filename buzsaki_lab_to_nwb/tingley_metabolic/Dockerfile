FROM python:3.9

WORKDIR /usr/src/

# Standard AWS interactive setup
RUN stty intr \^k  # re-assign commands for copy for use during manual login

# Does conda come with python:3.9? Does git come with conda?
#RUN wget https://repo.anaconda.com/archive/Anaconda3-2020.07-Linux-x86_64.sh
#RUN bash Anaconda3-2020.07-Linux-x86_64.sh
#RUN conda install git
RUN git clone https://github.com/catalystneuro/buzsaki-lab-to-nwb
RUN cd buzsaki-lab-to-nwb
RUN git checkout run_on_aws
RUN conda env create -f tingley_metabolic_environment.yml
RUN conda activate buzsaki_tingley_metabolic
RUN pip install -e .
RUN cd ..
RUN git clone https://github.com/catalystneuro/nwb-conversion-tools
RUN cd nwb-conversion-tools
RUN pip install -e .

RUN sudo yum install tk tcllib
RUN wget https://downloads.globus.org/globus-connect-personal/linux/stable/globusconnectpersonal-latest.tgz
RUN tar xzf globusconnectpersonal-latest.tgz

# For manual step, need to then
#./globusconnectpersonal-3.1.6/globusconnectpersonal -setup


