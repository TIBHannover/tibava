Vagrant.configure("2") do |config|
  config.vm.box = "generic/debian12"

  # Configure network
  config.vm.network "private_network", ip: "192.168.56.10"

  # --- Ansible Provisioning Section ---
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "deploy.yml"
  end

  config.vm.provider "libvirt" do |vb|
    # Map more CPU cores (e.g., 2 or 4 depending on your host)
    vb.cpus = 4

    # Give it more RAM (e.g., 4096MB = 4GB, or 8192MB = 8GB)
    vb.memory = 8192
    vb.machine_virtual_size = 256
  end
end