import subprocess

def run_subprocess(command, logger):

        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            stdout, stderr = proc.communicate()
            returncode = proc.wait()

        for line in stdout.splitlines():
                logger.debug(line.strip())

        if stderr:
            for line in stderr.splitlines():
                logger.debug(line.strip())
            
        if returncode != 0:
            raise Exception(f"Command '{' '.join(command)}' returned non-zero exit status {returncode}")
        return