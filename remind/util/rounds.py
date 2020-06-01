import datetime as dt

_NONSTANDARD_CONTEST_INDICATORS = [
    'wild',
    'fools',
    'unrated',
    'surprise',
    'unknown',
    'friday',
    'q#',
    'testing',
    'marathon',
    'kotlin',
    'onsite',
    'experimental',
    'abbyy'
]

_STANDARD_CONTEST_INDICATORS = [
    'rated for',
    'cook-off',
    'lunchtime',
    'atcoder grand contest',
    'atcoder beginner contest',
    'atcoder regular contest',
    'arc:',
    "srm",
    'tco20 round',
    'code jam round',
    'kick start round',
    'codeforces round #'
]

_WEBSITES = [
    'codechef.com',
    'codeforces.com',
    'atcoder.jp',
    'topcoder.com',
    'codingcompetitions.withgoogle.com'
]


def is_nonstandard_contest(contest):
    return any(string in contest.name.lower()
               for string in _NONSTANDARD_CONTEST_INDICATORS)


class Rounds:
    def __init__(self, round):
        self.id = round['id']
        self.name = round['event']
        self.start_time = dt.datetime.strptime(
            round['start'], '%Y-%m-%dT%H:%M:%S')
        self.duration = dt.timedelta(seconds=round['duration'])
        self.url = round['href']
        self.website = round['resource']['name']
        self.website_id = round['resource']['id']

    def __str__(self):
        st = "ID = " + str(self.id) + ", "
        st += "Name = " + self.name + ", "
        st += "Start_time = " + str(self.start_time) + ", "
        st += "Duration = " + str(self.duration) + ", "
        st += "URL = " + self.url + ", "
        st += "Website = " + self.website + ", "
        st += "Website_id = " + str(self.website_id) + ", "
        st = "(" + st[:-2] + ")"
        return st

    def is_rated(self):

        if self.website not in _WEBSITES:
            return False

        for standard_indicator in _STANDARD_CONTEST_INDICATORS:
            if standard_indicator in self.name.lower():
                return True

        for non_standard_indicator in _NONSTANDARD_CONTEST_INDICATORS:
            if non_standard_indicator in self.name.lower():
                return False

        return False

    def __repr__(self):
        return "Round - " + self.name
