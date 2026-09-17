#coding=utf-8
# 功能：通过python程序远程执行命令
# 日期：2023年6月6日
import paramiko,time

def ssh(hostname, username, password):
    command = input('请输入需要执行的命令:')
    # 通过类SSHClint创建一个SSH_Client客户端对象
    SSH_Client = paramiko.SSHClient()
    # 自动接收服务器发来的密钥(模拟手工输入的yes)
    SSH_Client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
    try:  # 连接服务器
        SSH_Client.connect(hostname=hostname, username=username, password=password, port=22)
    except paramiko.ssh_exception.AuthenticationException:
        print("服务器账号或密码错误")
        exit(1)
    except Exception as error:
        print(f"服务器连接错误 原因是{error}")
        exit(1)
    xshell = SSH_Client.invoke_shell()  # 激活终端
    print("客户端连接成功")
    xshell.send(f"{command}\n")  # 通过激活终端发送(send)指令
    time.sleep(1)
    print(xshell.recv(65535).decode(encoding="utf-8"))  # 通过激活终端接收（recv）数据
    SSH_Client.close()


def sftp(hostname, username, password):
    try:
        SSH_transport = paramiko.Transport(hostname, 22) # 新建会话
    except Exception as error:
        print(f"服务器连接错误 原因是{error}")
        exit(1)
    try:
        SSH_transport.connect(username=username, password=password) # 通过会话连接
    except paramiko.ssh_exception.AuthenticationException:
        print("服务器账号或密码错误")
        exit(1)
    except Exception as error:
        print(f"服务器连接错误 原因是{error}")
        exit(1)
    ssh_SFTP = paramiko.SFTPClient.from_transport(SSH_transport) # 创建客户端
    print("客户端连接成功\n")
    while True:
        print("请输入sftp操作选项:\n")
        user_input = input("1.上传文件\n2.文件改名\n3.下载文件:\n")
        if user_input == "1" :
            src_file = input("请输入源文件的文件路径：")
            dst_file = input("请输入目的的文件路径：")
            ssh_SFTP.put(src_file, dst_file) # 上传文件
            break
        elif user_input == "2" :
            src_file = input("请输入源文件的文件路径：")
            dst_file = input("请输入的改名后的文件路径：")
            ssh_SFTP.rename(src_file, dst_file) # 改名
            break
        elif user_input == "3" :
            src_file = input("请输入源文件的文件路径：")
            dst_file = input("请输入下载位置的路径与文件名：")
            ssh_SFTP.get(dst_file, src_file) # 下载文件
            break
        else :
            print("输入的选项错误，请重新输入")
            continue
    print("操作完成")
    SSH_transport.close()


if __name__ == '__main__':
    ip = input("请输入需要连接的ip地址:")
    username = input("请输入用户名:")
    password = input("请输入密码:")
    user_input = input("1.ssh连接\n2.sftp连接:\n")
    if user_input == '1':
        print(f"\n{'*' * 50}")
        ssh(ip, username, password)
    elif user_input == '2':
        print(f"\n{'*' * 50}")
        sftp(ip, username, password)
    else:
        exit(1)