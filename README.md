
# vagrant-ansible-docker

Deploying a web application on a Digital Ocean VPS server using 
[Vagrant](https://www.vagrantup.com/), [Ansible](https://www.ansible.com/), 
[Docker](https://www.docker.com/) and [Consul](https://www.consul.io/).

## How it works

Deploy a simple web application with one single command:

* `vagrant up`
  Fires up a Digital Ocean VPS setting up SSH keys and starts Ansible on it.

* Ansible will set up the server according to the playbook.

* The playbook includes setting up repositories for Docker and its 
  installation.

* It also retrievs three Docker containers from [Docker 
  Hub](https://hub.docker.com/) i.e. [Debian 
slim](https://hub.docker.com/_/debian/), 
  [PostgreSQL](https://hub.docker.com/_/postgres/) and 
[Consul](https://hub.docker.com/_/consul/).

* Docker containers will also be set up by Ansible using [Ansible 
  Container](https://www.ansible.com/ansible-container).

* After invoking the containers Ansible will put the connection settings in 
  [Consuls Key/Value 
store](https://www.consul.io/intro/getting-started/kv.html) using 
[python-consul](https://github.com/cablehead/python-consul).

*  Finally Ansible launches the Debian container, bind mounting the 
   application directory and setting a script for launching the app as entry point. 


## Installation

### Vagrant

Having a Debian deployment host at hand Vagrant and Ansible can easily be 
installed using Debian package management system:

    apt-get install vagrant zlib1g-dev rsync

This setup involves Vagrant version 1.6.5 and Ansible version 2.2.1.0 which 
s available for Debian Jessie via *backports* repository:

    echo 'deb http://ftp.debian.org/debian jessie-backports main' > \
      /etc/apt/sources.list.d/jessie-backports.list

    apt-get install -t jessie-backports ansible

Choosing a project folder like `/vagrant` requires initialization:

    cd /vagrant
    vagrant init

Vagrant can be extended via plugins to support Digital Ocean API for 
deployment of virtual private servers, i.e.

    vagrant plugin install vagrant-digitalocean

The initialization will set up a file called `Vagrantfile` which configures 
also the connection to the virtual server provider. In order to use Digital 
Ocean here one can set it up to use it as default provider and set the API 
token via environment variable:

    export VAGRANT_DEFAULT_PROVIDER=digital_ocean
    export DIGITAL_OCEAN_ACCESS_TOKEN=...

Some adjustments to `Vagrantfile` are necessary:

    # config.vm.box = "base"
      config.vm.box = "digital_ocean"
      config.ssh.private_key_path = "~/.ssh/id_rsa"
    
      config.vm.provider :digital_ocean do |provider|
          raise RuntimeError, "No Digital Ocean access token has been set. Set the 
    \
    DIGITAL_OCEAN_ACCESS_TOKEN environment variable." unless 
    ENV["DIGITAL_OCEAN_ACCESS_TOKEN"]
          provider.token = ENV["DIGITAL_OCEAN_ACCESS_TOKEN"]
          provider.image = 'debian-8-x64'
          provider.region = 'fra1'
          provider.size = '512mb'
      end
    
      config.vm.define "vm-docker"
      config.vm.hostname = "vm-docker"
    
      config.vm.provision "ansible" do |ansible|
          ansible.playbook = "provisioning/playbook.yml"
      end


This will basically configure Debian as deployment image and a host called 
`vm-docker`. One can exclude the `Vagrantfile` and a the git repository by add 
ing:

    config.vm.synced_folder ".", "/vagrant", type: "rsync", rsync__exclude: [ "Vagrantfile", ".git/" ]


### Ansible

Ansible project folder is set to

    /vagrant/provisioning

and the playbook for this deplyment is called `playbook.yml`.

This file starts with declarations about packages which have to be installed 
on the vm and adding a Docker repository there:

    deb https://apt.dockerproject.org/repo debian-jessie main

The package `docker-engine` will be installed and the following containers 
declared to be retrieved:

    pull consul image from https://hub.docker.com/_/consul/
    pull postgres image from https://hub.docker.com/_/postgres/
    pull debian image for web app from https://hub.docker.com/_/debian/

For **Consul** setup it should have at least a persistent data directory and a 
configuration directory will be added, too:

    mkdir -p /vagrant/consul/config /vagrant/consul/data

They will be mounted into the container giving the following playbook script:

    - name: "Launch consul container"
      docker_container:
        name: consul
        image: consul
        state: started
        recreate: yes
        log_driver: journald
        volumes:
          - /vagrant/consul/config:/consul/config:ro
          - /vagrant/consul/data:/consul/data:rw
        entrypoint: consul agent -config-dir=/consul/config
        published_ports: "{{ bridgeip }}:8500:8500"

Consul configuration is stored in json format, i.e.

    /vagrant/consul/config/consul.json


The **PostgreSQL** container is also set up with a persistent data directory 
and additionally a password is set via environment variable:

    - name: "Launch database container"
      docker_container:
        name: db
        image: postgres
        state: started
        restart: yes
        log_driver: journald
        env:
          POSTGRES_PASSWORD: "..."
          PGDATA: "/var/lib/postgresql/data/pgdata"
        volumes:
          - /vagrant/pgsql/data:/var/lib/postgresql/data/pgdata:rw


In order to make use of Consuls Key/Value store Ansible has a module for 
interacting with Consul. It requires the `python-consul` package.

    - name: Install consul python library
      pip: name=python-consul
    - name: add postgresql coordinates to consul kv store
      consul_kv: host="{{ bridgeip }}" key=postgresql/host value=db
    - name: add postgresql coordinates to consul kv store
      consul_kv: host="{{ bridgeip }}" key=postgresql/port value=5432
    - name: add postgresql coordinates to consul kv store
      consul_kv: host="{{ bridgeip }}" key=postgresql/user value=postgres
    - name: add postgresql coordinates to consul kv store
      consul_kv: host="{{ bridgeip }}" key=postgresql/password value="..."


Finally the set up the **application** container is done via:

    - name: "Launch application container"
      docker_container:
        name: app
        hostname: app
        image: debian
        state: started
        recreate: yes
        log_driver: journald
        published_ports: 80:8080
        volumes:
          - /vagrant/application:/srv/application:ro
        entrypoint: /bin/sh /srv/application/run.sh
        links:
          - consul
          - db

The linking of the containers induces Docker to set up environment variables 
for the other containers and host entries in `/etc/hosts` there. The web 
application makes use of the environment variables to find the Consul server 
and also uses the entry in `/etc/hosts` in order to resolve the IP address of 
*db*.


### Web application

The web application container gets set up via `vagrant/application/run.sh` 
script. It involves the installation of additionally needed packages and 
launching the app via:

    python ${APP_PATH}/server.py

Upon application start it connects to the Consul server found by environment 
variables and detects the connection parameters for the PostgreSQL instance by 
it.


## Outlook

This set up is a proof of concept for the deployment of web applications via 
Vagrant, Ansible and Docker using Consul for the configuration of the database 
connection. Using Consuls Key/Value store is an elegant approch and can be 
driven further by launching consul binaries in every container for publishing 
Docker containers services directly by it.

