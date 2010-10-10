#!/usr/bin/env python

# Copyright (c) 2009-2010 Anthony Williams
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from optparse import OptionParser
import os, re, sys, random, shutil, yaml

def is_enabled_filter(filter_string):
    """ Returns whether the given filter string indicates that matching shows
        should be enabled, rather than disabled.
    """
    try:
        return filter_string[0] != "-"
    except IndexError, e:
        return False

def playlist_entry(episode):
  return "#EXTINFO:0," + episode.split('/')[-1] + "\n" + episode

def playlist_contents(episodes):
    """ Creates the contents of a playlist file for a given array of episode
        paths.
    """
    playlist = "#EXTM3U\n"
    playlist += "\n".join([playlist_entry(episode) for episode in episodes])
    return playlist

class Show(object):
    def __init__(self, name, base_path='.'):
        """ Shows represent a series of media files
        """
        self.name = name
        self.eplist = []
        self.path = base_path + "/" + name
        self.enabled = False

    def episodes(self):
        """ Returns an array containing paths to media files belonging to this
            Show.
        """
        if not self.eplist:
            self.eplist = self.__episodes_for_path(self.path)
        return self.eplist

    def name_in_colour(self):
        """ Returns the show name, in green or red depending on whether the
            show is enabled.
        """
        out = (self.enabled and "\033[32m") or "\033[31m"
        out += self.name + " \033[30m(" + str(len(self.episodes())) + ")\033[0m"
        return out

    def __episodes_for_path(self, path):
        """ Gets a list of media files in the given directory, and subdirectories.
        """
        files = []
        ext = re.compile(r".*(avi|mpg|mpeg|mp4|mkv|vob)$")
        for node in os.listdir(path):
            node = os.path.join(path, node)
            if os.path.isfile(node):
                if ext.match(node): files.append(node)
            elif os.path.isdir(node):
                for nested_node in self.__episodes_for_path(node):
                    if ext.match(nested_node): files.append(nested_node)
        return files

class ShowList(object):
    def __init__(self):
        self.shows = {}
        self.filters = {}

    def add_show(self, name, abbrev=None, base_path='.'):
        self.shows[name] = Show(name, base_path=base_path)
        self.add_filter(abbrev, [self.shows[name]])
        return self

    def add_filter(self, match, shows=[]):
        self.filters[match] = Filter(match, shows)
        return self

    def add_group(self, match, filter_string):
        self.filters[match] = Group(match, filter_string, self)
        return self

    def filter(self, filter_string):
        """Filters the showlist according to the given filter_string."""
        all_pseudo_filter = re.compile(r"^-?all$")

        for token in filter_string.split(" "):
            enable_or_disable = is_enabled_filter(token)
            if all_pseudo_filter.match(token):
                for show in self.shows.values():
                    show.enabled = enable_or_disable
            else:
                for filter in self.filters.values():
                    if filter.match(token):
                        filter.run(enable_or_disable)
                        break
        return self

    def random_episodes(self, count=5):
        """ Returns an array of paths to episodes which match the currently
		    enabled filters.
        """
        all_matching_episodes = []

        for show in self.shows.values():
          if show.enabled:
            all_matching_episodes.extend(show.episodes())

        random.shuffle(all_matching_episodes)
        return all_matching_episodes[0:count]

    def shortcuts(self):
        keys = self.filters.keys()
        keys.sort()

        shorts = []
        groups = []

        for name in keys:
            if self.filters[name].__class__ != Filter:
                groups.append(name)
            else:
                shorts.append(name.rjust(20) + " : " + ", ".join([
                    show.name_in_colour() for show in self.filters[name].shows]))

        return ("Groups : ".rjust(23) + " ".join(groups) + "\n\n" +
            "\n".join(shorts))

class Filter(object):
    """ Filters operate on a showlist, using a "match" string to enable shows.
        For example, the match string "wliia" might be used to enable "Whose
        Line Is It Anyway?".
    """
    def __init__(self, match, shows):
        self.regex = re.compile(r"^-?" + match)
        self.shows = shows

    def match(self, against):
        return self.regex.match(against)

    def run(self, enable=True):
        for show in self.shows:
            show.enabled = enable

class Group(object):
    def __init__(self, match, filter_string, showlist):
        self.regex = re.compile(match)
        self.filter_string = filter_string
        self.showlist = showlist

    def match(self, against):
        return self.regex.match(against)

    def run(self, _):
        self.showlist.filter(self.filter_string)

# Set up the script ==========================================================

if __name__ == "__main__":
    shows = ShowList()

    with open("playlist.yml", "r") as f:
        config = yaml.load(f.read())
        for show in config["shows"]:
            shows.add_show(show["name"], show["filter"], config["path"])
        for group_name, group_items in config["groups"].items():
            shows.add_group(group_name, group_items)

    # Aaaaand, go! ===========================================================

    optparser = OptionParser(usage="playlist.py [options] [filters]")

    optparser.add_option("-c", "--count", type="int", default=5,
        help="Number of episodes to playlist")
    optparser.add_option("-q", "--no-play", action="store_true",
        help="Don't launch VLC")
    optparser.add_option("-l", "--list", action="store_true",
        help="List all the filters")
    optparser.add_option("--copy", type="string", default=False,
        help="Copies the media files to the given directory, and creates " \
             "the playlist there")

    if config['args'] and len(config['args']) > 0:
        args = [sys.argv[0]]
        args.extend(config['args'].split(" "))
        args.extend(sys.argv[1:len(sys.argv)])
    else:
        args = sys.args

    (options, args) = optparser.parse_args(args)

    shows.filter(" ".join(args))

    if options.list:
        print shows.shortcuts()
    else:
        episodes = shows.random_episodes(options.count)
        playlist_path = "playlist.m3u"

        if options.copy:
            # Copy the media files to another directory, and create the
            # playlist there.
            playlist_path = options.copy + "/" + playlist_path
            orig_episodes = episodes
            episodes      = []

            for episode in orig_episodes:
                new_path = options.copy + "/" + episode.split("/")[-1]
                print "Copying " + episode.split("/")[-1]
                shutil.copy2(episode, new_path)
                episodes.append(new_path)

        with open(playlist_path, "w") as f:
            f.write(playlist_contents(episodes))
        if not options.no_play:
            os.system("open '" + playlist_path + "'")
