import paramiko
import logging
from paramiko.ssh_exception import SSHException, AuthenticationException

class SSHClient:
    def __init__(self, host, user, password=None, key_path=None, port=22):
        """
        Initializes the SSH client with given credentials.
        :param host: Hostname or IP address of the server.
        :param user: Username to connect with.
        :param password: Password for SSH (optional).
        :param key_path: Path to the private SSH key (optional).
        :param port: Port for SSH connection (default: 22).
        """
        self.host = host
        self.user = user
        self.password = password
        self.key_path = key_path
        self.port = port
        self.logger = logging.getLogger("ssh_utils")
        self.client = None

    def connect(self):
        """
        Establish an SSH connection to the host.
        """
        if self.client is not None and self.client.get_transport() and self.client.get_transport().is_active():
            self.logger.info(f"Already connected to {self.host}. Reusing the connection.")
            return

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using password or private key
            if self.password:
                self.client.connect(
                    hostname=self.host, 
                    username=self.user, 
                    password=self.password, 
                    port=self.port,
                    timeout=10
                )
            elif self.key_path:
                private_key = paramiko.RSAKey.from_private_key_file(self.key_path)
                self.client.connect(
                    hostname=self.host, 
                    username=self.user, 
                    pkey=private_key, 
                    port=self.port,
                    timeout=10
                )
            else:
                raise ValueError("Either password or key_path must be provided for SSH connection.")
            
            self.logger.info(f"Successfully connected to {self.host} on port {self.port}")

        except AuthenticationException:
            self.logger.error(f"Authentication failed for {self.host}. Check credentials or key file.")
            raise
        except SSHException as ssh_ex:
            self.logger.error(f"SSH error while connecting to {self.host}: {str(ssh_ex)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while connecting to {self.host}: {str(e)}")
            raise

    def execute_command(self, command, timeout=30):
        """
        Execute a command on the remote server.
        :param command: Command to execute.
        :param timeout: Timeout in seconds for command execution.
        :return: Tuple (output, error, exit_code).
        """
        if self.client is None or not (self.client.get_transport() and self.client.get_transport().is_active()):
            self.connect()

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()

            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()

            if exit_status == 0:
                self.logger.info(f"Command executed successfully on {self.host}: {command}")
                return output, error, exit_status
            else:
                self.logger.warning(f"Command execution failed on {self.host} with exit status {exit_status}")
                return output, error, exit_status

        except SSHException as ssh_ex:
            self.logger.error(f"SSH error while executing command on {self.host}: {str(ssh_ex)}")
            raise
        except Exception as e:
            self.logger.error(f"Error executing command on {self.host}: {str(e)}")
            # Attempt to reconnect and execute the command again
            self.close()
            self.connect()  # Re-establish the connection
            return self.execute_command(command, timeout)

    def close(self):
        """
        Close the SSH connection.
        """
        if self.client:
            try:
                self.client.close()
                self.logger.info(f"SSH connection closed for {self.host}")
            except Exception as e:
                self.logger.error(f"Error while closing SSH connection to {self.host}: {str(e)}")
            finally:
                self.client = None

    def __enter__(self):
        """
        Context manager entry.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit - ensure the SSH connection is closed.
        """
        self.close()

    def is_connected(self):
        """
        Check if the SSH client is connected and transport is active.
        :return: True if connected, False otherwise.
        """
        return self.client is not None and self.client.get_transport() and self.client.get_transport().is_active()
