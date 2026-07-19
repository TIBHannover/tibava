Vagrant.configure("2") do |config|
  config.vm.box = "generic/debian12"

  # Configure network
  config.vm.network "private_network", ip: "192.168.56.10"

  # --- Ansible Provisioning Section ---
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "deploy.yml"
  end
end