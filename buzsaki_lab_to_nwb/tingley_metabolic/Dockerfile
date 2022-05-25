FROM python:3.9
WORKDIR /usr/src/
RUN git clone https://github.com/catalystneuro/buzsaki-lab-to-nwb

FROM python:3.9
WORKDIR /usr/src/buzsaki-lab-to-nwb
RUN git checkout run_on_aws \
  && pip install -r tingley_metabolic_requirements.txt

FROM python:3.9
WORKDIR /usr/src/
RUN sudo apt-get install tk tcllib \
  && wget https://downloads.globus.org/globus-connect-personal/linux/stable/globusconnectpersonal-latest.tgz \
  && tar xzf globusconnectpersonal-latest.tgz

# Standard AWS interactive setup
CMD ["stty", "intr", "\^k"]  # re-assign commands for copy for use during manual login

# For manual step, need to then
#./globusconnectpersonal-3.1.6/globusconnectpersonal -setup


