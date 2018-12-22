import subprocess as sp
import os

# Silly utilities to help us track what version of things we are using

def get_git_hash(repo_path):
    try:
        git_hash = sp.check_output(['git', 'rev-parse', '--short', 'HEAD'], universal_newlines=True,
                                    cwd=repo_path).strip()
        git_url = sp.check_output(['git', 'config', '--get', 'remote.origin.url'], universal_newlines=True,
                                    cwd=repo_path).strip()
        if git_url.startswith('git@'):
            git_url = git_url[4:]
        # Got git hash successfully
        return git_url, git_hash
    except: #sp.CalledProcessError:
        # Unknown git hash
        return '',''

def get_field(field_name, file_name, module_path, delimiter=':'):
    value = sp.check_output(['grep', field_name, file_name], universal_newlines=True,
                                cwd=module_path).strip()
    value = value.split(delimiter, 1)[1].strip().rstrip(',')
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    else:
        return value


def get_npm_module_version(module_path):
    try:
        # print('module_path', module_path)
        resolved = get_field('resolved', 'package.json', module_path, ':')
        version = get_field('version', 'package.json', module_path, ':')
        return version,resolved
    except: #sp.CalledProcessError:
        return '',''

def get_version(module_path):
    try:
        # print('module_path', module_path)
        version = get_field('version', 'setup.py', module_path, '=')
        return version
    except: #sp.CalledProcessError:
        return ''
    
def get_versions(script_path):
    stk_path = os.path.realpath(os.path.join(script_path, '../server/node_modules/sstk'))
    root_path = os.path.realpath(os.path.join(script_path, '../..'))
    sim_version = get_version(root_path)
    stk_version, stk_resolved = get_npm_module_version(stk_path)
    sim_git, sim_git_hash = get_git_hash(root_path)
    sim_git_str = sim_git + '#' + sim_git_hash if len(sim_git) > 0 else ''
    stk_git, stk_git_hash = get_git_hash(stk_path)
    stk_git_str = stk_git + '#' + stk_git_hash if len(stk_git) > 0 else ''
    sim_version = '#'.join([x for x in [sim_version, sim_git_str] if len(x) > 0])
    if stk_git == sim_git:
        # Same git repo
        stk_version = '#'.join([x for x in [stk_version, stk_resolved] if len(x) > 0])
    else:
        stk_version = '#'.join([x for x in [stk_version, stk_git_str] if len(x) > 0])
    return {
        "stk_version": stk_version,
        "sim_version": sim_version
    }
