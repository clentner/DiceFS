#!/usr/bin/env python
'''
    Implements a randomized filesystem. Directories in the /exist directory
    will exist with a probability equal to their filename. So half the time
    you query (e.g. with test or /usr/bin/[ -e) /exist/0.5, you will get a
    positive response.

    Directory listings (e.g. ls -l) of /exist will return a single entry with
    a randomly chosen filename between zero and one. Of course, when you query
    its attributes, it might not exist!

    Function docstrings are a combination of python docs, man page entries,
    fusepy docstrings, and author notes.
'''

from __future__ import with_statement

from errno import EACCES
from os.path import realpath
from sys import argv, exit
from threading import Lock

import errno
import time
import os
import stat
import random

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn


class Exist(LoggingMixIn, Operations):
    '''
    A filesystem where files pop in and out of existence. Any file in the
    `exist` directory has its name interpreted as a probability in [0, 1].
    Any given query (access, getattr, etc) will succeed with that probability.
    Files not in the format exist/[01].\d+ never exist.
    '''
    def __init__(self):
        pass

    def __call__(self, *args):
        # for debugging purposes
        print('>>>', *args)
        res = super(Exist, self).__call__(*args)
        print(res)
        return res

    def _exists(self, path):
        '''
        Internal method that does the dice-rolling to determine whether or not
        a file exists.
        @param path The file path to check. To have a chance at existing,
            must be in the exist/ directory, and the filename must be a number
            between 0 and 1 (inclusive).
        @return True iff the file exists right now.
        '''
        if (path in ('/', '/exist')):
            return True
        if (path[:7] != '/exist/'):
            return False
        
        filename = path[7:]
        try:
            probability = float(filename)
        except ValueError:
            return False
        if (not (0 <= probability <= 1)):
            return False

        rand = random.random()
        return (rand <= probability)

    def _mode(self):
        '''
        Random access mode, chosen to be a valid triple.
        '''
        user = random.randint(0, 7)
        group = random.randint(0, 7)
        world = random.randint(0, 7)
        return ((user << 6) | (group << 3) | (world))

    def _size(self):
        '''
        Random file size, in bytes. Chosen arbitrarily to not be too big.
        '''
        return random.randint(0, 2**30)

    def _timestamp(self):
        '''
        Random unix timestamp, from Jan 1, 1970 up to today.
        '''
        return random.uniform(0, time.time())

    def _id(self):
        '''
        Random uid or gid, from 1 to the arbitrarily-chosen hundred thousand.
        '''
        return random.randint(1, 10**5)

    
    # Return our gid to make the os happy
    _gid = os.getgid
    _uid = os.getuid


    def access(self, path, mode):
        '''
        Test for access to `path`.
        @param mode F_OK to test the existence of path, or the inclusive OR of
            one or more of R_OK, W_OK, and X_OK to test permissions.
        Implementation details: return None on exists/good permissions;
            raise FuseOSError(EACESS) on nonexistent/bad permissions.
        '''
        if (path in ('/', '/exist')):
            return
        # You can't write to anything here
        if (mode & os.W_OK):
            raise FuseOSError(EACCES)
        # Otherwise, roll the dice.
        if (not self._exists(path)):
            raise FuseOSError(EACCES)


    def getattr(self, path, fh=None):
        '''
        Get a file's attributes. Called all the time; the only call `ls` makes.
        Implementation details: return a dictionary containing these keys:
            - st_atime - time of most recent access
            - st_ctime - platform dependent; time of most recent metadata
                change on Unix, or the time of creation on Windows
            - st_gid - group id of owner
            - st_mode - protection bits
            - st_mtime - time of most recent content modification
            - st_nlink - number of hard links
            - st_size - filesize in bytes
            - st_uid - user id of owner
        '''
        if (not self._exists(path)):
            raise FuseOSError(errno.ENOENT)

        '''
        mode = self._mode()
        # Need to set the directory bit on the mode or file managers will
        # reject the filesystem.
        if path in ('/', '/exist'):
            mode |= stat.S_IFDIR
        '''

        mode = stat.S_IFDIR | 0o775
        attr = {'st_atime': self._timestamp(),
                'st_ctime': self._timestamp(),
                'st_mtime': self._timestamp(),
                'st_gid': self._gid(),
                'st_uid': self._uid(),
                'st_mode': mode,
                'st_nlink': 1,
                'st_size': self._size()
                }
        return attr
                


    def readdir(self, path, fh):
        '''
        Return a directory listing
        '''
        if (path == '/'):
            return ['.', '..', 'exist']
        # return a random folder too.
        return ['.', '..', str(random.random())]


    def statfs(self, path):
        '''
        Return information about the filesystem itelf. `path` is the pathname
        of any file within the mounted file system.
        returns a dictionary with the following keys, like C statvfs():
            - f_bavail: free blocks for unprivileged users
            - f_bfree: free blocks
            - f_blocks: file system size in fragment size units
            - f_bsize: block size
            - f_favail: free inodes for unprivileged users
            - f_ffree: free inodes
            - f_files: inodes
            - f_flag: mount flags
            - f_frsize: fragment size
            - f_namemax: maximum filename length
        '''
        # Totally random sizes for all
        return dict((key, self._size()) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    #Not implemented (unnecessary)
    chmod = None
    chown = None
    create = None
    flush = None
    fsync = None
    getxattr = None
    link = None
    listxattr = None
    mkdir = None
    mknod = None
    open = None
    read = None
    readlink = None
    release = None
    rename = None
    rmdir = None
    symlink = None
    truncate = None
    unlink = None
    utimens = None
    write = None


if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    fuse = FUSE(Exist(), argv[1], foreground=True)
