sudo vi /etc/sysctl.conf

vm.overcommit_memory = 1

sudo sysctl -p

# 运行本目录下的test_redis.py文件，可验证redis是否部署成功
