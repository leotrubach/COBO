import subprocess
import sys
import scipy
import scipy.optimize

args = sys.argv[1:]

correlation = 0

# d=20, pv=10 previous setting

depth = int(args[1])
engine = args[0]
multipv = 1
verbose = False


def get_pars():
    sf = subprocess.Popen('./' + engine, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, bufsize=1)
    sf.stdin.write('isready' + '\n')
    pars = []
    while True:
        outline = sf.stdout.readline().rstrip()
        print outline
        if outline == 'readyok':
            break
        if not outline.startswith('Stockfish'):
            pars.append(outline.split(','))

    return pars


Pars = get_pars()


def launch_sf(locpars):
    if verbose:
        for p in locpars:
            print p[0], p[1]
    sf = subprocess.Popen('./' + engine, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, bufsize=1)
    sf.stdin.write('setoption name multipv value ' + str(multipv) + '\n')
    sf.stdin.write('setoption name Hash value 16' + '\n')

    for par in locpars:
        cmd = 'setoption name ' + par[0] + ' value ' + str(par[1]) + '\n'
        sf.stdin.write(cmd)

    sf.stdin.write('go depth ' + str(depth) + '\n')
    sf.stdin.write('bench 16 1 ' + str(depth - 10) + ' balancedMiddlegames.epd\n')
    sf.stdin.write('bench 16 1 ' + str(depth - 13) + ' balancedEndgames.epd\n')
    how_many_benches = 0


    while True:
        if how_many_benches == 2:
            break
        outline = sf.stdout.readline().rstrip()
        if outline.startswith('Search/eval correlation'):
            correlation_line = outline
            print '\r' + outline + ' ',
        if outline.startswith('info depth') and verbose:
            print '\n' + outline + ' ',

        if outline.startswith('Total time'):
            how_many_benches += 1

    result = float(correlation_line.split()[2])
    if verbose:
        print '\n' + str(result)
    sf.kill()
    return result


def array2pars(pars_array):
    locpars = Pars
    for n, par in enumerate(locpars):
        locpars[n][1] = int(round(float(pars_array[n])))
    return locpars


def pars2array(pars):
    pars_array = [par[1] for par in pars]
    return pars_array


def fitness(parsArray):
    locpars = array2pars(parsArray)
    return -launch_sf(locpars)


def get_bounds():
    return [(p[2], p[3]) for p in Pars]


def status_msg(xk, convergence=0):
    new_pars = array2pars(xk)
    print
    for p in new_pars:
        print p[0], p[1]
    print
    return False


if __name__ == '__main__':
    f = fitness(pars2array(Pars))
    print
    '\n' + 'Reference correlation: ' + str(-f)
    res = scipy.optimize.differential_evolution(fitness, get_bounds(), disp=True, callback=status_msg)
    status_msg(res.x)
    print 'Search/eval correlation: ', -res.fun
