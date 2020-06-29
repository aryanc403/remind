import datetime as dt


class Round:
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

    def is_desired(
            self,
            website_allowed_patterns,
            website_disallowed_patterns):
        for disallowed_pattern in website_disallowed_patterns[self.website]:
            if disallowed_pattern in self.name.lower():
                return False
            if disallowed_pattern in self.url.lower():
                return False

        for allowed_pattern in website_allowed_patterns[self.website]:
            if allowed_pattern in self.name.lower():
                return True
        return False

    def __repr__(self):
        return "Round - " + self.name
