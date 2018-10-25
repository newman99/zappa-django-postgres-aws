FROM lambci/lambda:build-python3.6

ENV PYTHONUNBUFFERED 1

MAINTAINER "Matthew Newman" <newman99@gmail.com>

WORKDIR /var/task
COPY requirements.txt /var/task
RUN pip install -r requirements.txt
COPY . /var/task

# Fancy prompt to remind you are in zappashell
RUN echo 'export PS1="\[\e[36m\]zappashell>\[\e[m\] "' >> /root/.bashrc

# Enter virtual environment at login
RUN echo 'source /var/task/ve/bin/activate' >> /root/.bashrc

# Additional RUN commands here
# RUN yum clean all && \
#    yum -y install <stuff>

CMD ["bash"]
