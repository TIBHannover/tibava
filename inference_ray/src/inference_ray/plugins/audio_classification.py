from typing import List, Tuple, Callable, Dict, BinaryIO

from pathlib import Path
import sys

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import AudioData, ListData, Annotation, ShotsData, AnnotationData
from tibava_data import DataManager, Data

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "top_k": 3,
    "threshold": 0.5,
}

requires = {
    "shots": ShotsData,
    "audio": AudioData,
}

provides = {"annotations": AnnotationData}

"""
Additional files needed in data/models/audio_classification/
ontology.json: from fakenarratives repo
beats: git cloned and beats subfolder extracted from https://huggingface.co/spaces/fffiloni/SALMONN-7B-gradio/tree/677c0125de736ab92751385e1e8664cd03c2ce0d/beats (not available anymore)
    original repo/folder: https://github.com/microsoft/unilm/tree/master/beats
model from https://onedrive.live.com/?authkey=%21APLo1x9WFLcaKBI&id=6B83B49411CA81A7%2125955&cid=6B83B49411CA81A7&parId=root&parQt=sharedby&o=OneUp
"""

AUDIO_CLASSIFICATION_VOCAB = {
    0: "Speech",
    1: "Male speech, man speaking",
    2: "Female speech, woman speaking",
    3: "Child speech, kid speaking",
    4: "Conversation",
    5: "Narration, monologue",
    6: "Babbling",
    7: "Speech synthesizer",
    8: "Shout",
    9: "Bellow",
    10: "Whoop",
    11: "Yell",
    12: "Battle cry",
    13: "Children shouting",
    14: "Screaming",
    15: "Whispering",
    16: "Laughter",
    17: "Baby laughter",
    18: "Giggle",
    19: "Snicker",
    20: "Belly laugh",
    21: "Chuckle, chortle",
    22: "Crying, sobbing",
    23: "Baby cry, infant cry",
    24: "Whimper",
    25: "Wail, moan",
    26: "Sigh",
    27: "Singing",
    28: "Choir",
    29: "Yodeling",
    30: "Chant",
    31: "Mantra",
    32: "Male singing",
    33: "Female singing",
    34: "Child singing",
    35: "Synthetic singing",
    36: "Rapping",
    37: "Humming",
    38: "Groan",
    39: "Grunt",
    40: "Whistling",
    41: "Breathing",
    42: "Wheeze",
    43: "Snoring",
    44: "Gasp",
    45: "Pant",
    46: "Snort",
    47: "Cough",
    48: "Throat clearing",
    49: "Sneeze",
    50: "Sniff",
    51: "Run",
    52: "Shuffle",
    53: "Walk, footsteps",
    54: "Chewing, mastication",
    55: "Biting",
    56: "Gargling",
    57: "Stomach rumble",
    58: "Burping, eructation",
    59: "Hiccup",
    60: "Fart",
    61: "Hands",
    62: "Finger snapping",
    63: "Clapping",
    64: "Heart sounds, heartbeat",
    65: "Heart murmur",
    66: "Cheering",
    67: "Applause",
    68: "Chatter",
    69: "Crowd",
    70: "Hubbub, speech noise, speech babble",
    71: "Children playing",
    72: "Animal",
    73: "Domestic animals, pets",
    74: "Dog",
    75: "Bark",
    76: "Yip",
    77: "Howl",
    78: "Bow-wow",
    79: "Growling",
    80: "Whimper (dog)",
    81: "Cat",
    82: "Purr",
    83: "Meow",
    84: "Hiss",
    85: "Caterwaul",
    86: "Livestock, farm animals, working animals",
    87: "Horse",
    88: "Clip-clop",
    89: "Neigh, whinny",
    90: "Cattle, bovinae",
    91: "Moo",
    92: "Cowbell",
    93: "Pig",
    94: "Oink",
    95: "Goat",
    96: "Bleat",
    97: "Sheep",
    98: "Fowl",
    99: "Chicken, rooster",
    100: "Cluck",
    101: "Crowing, cock-a-doodle-doo",
    102: "Turkey",
    103: "Gobble",
    104: "Duck",
    105: "Quack",
    106: "Goose",
    107: "Honk",
    108: "Wild animals",
    109: "Roaring cats (lions, tigers)",
    110: "Roar",
    111: "Bird",
    112: "Bird vocalization, bird call, bird song",
    113: "Chirp, tweet",
    114: "Squawk",
    115: "Pigeon, dove",
    116: "Coo",
    117: "Crow",
    118: "Caw",
    119: "Owl",
    120: "Hoot",
    121: "Bird flight, flapping wings",
    122: "Canidae, dogs, wolves",
    123: "Rodents, rats, mice",
    124: "Mouse",
    125: "Patter",
    126: "Insect",
    127: "Cricket",
    128: "Mosquito",
    129: "Fly, housefly",
    130: "Buzz",
    131: "Bee, wasp, etc.",
    132: "Frog",
    133: "Croak",
    134: "Snake",
    135: "Rattle",
    136: "Whale vocalization",
    137: "Music",
    138: "Musical instrument",
    139: "Plucked string instrument",
    140: "Guitar",
    141: "Electric guitar",
    142: "Bass guitar",
    143: "Acoustic guitar",
    144: "Steel guitar, slide guitar",
    145: "Tapping (guitar technique)",
    146: "Strum",
    147: "Banjo",
    148: "Sitar",
    149: "Mandolin",
    150: "Zither",
    151: "Ukulele",
    152: "Keyboard (musical)",
    153: "Piano",
    154: "Electric piano",
    155: "Organ",
    156: "Electronic organ",
    157: "Hammond organ",
    158: "Synthesizer",
    159: "Sampler",
    160: "Harpsichord",
    161: "Percussion",
    162: "Drum kit",
    163: "Drum machine",
    164: "Drum",
    165: "Snare drum",
    166: "Rimshot",
    167: "Drum roll",
    168: "Bass drum",
    169: "Timpani",
    170: "Tabla",
    171: "Cymbal",
    172: "Hi-hat",
    173: "Wood block",
    174: "Tambourine",
    175: "Rattle (instrument)",
    176: "Maraca",
    177: "Gong",
    178: "Tubular bells",
    179: "Mallet percussion",
    180: "Marimba, xylophone",
    181: "Glockenspiel",
    182: "Vibraphone",
    183: "Steelpan",
    184: "Orchestra",
    185: "Brass instrument",
    186: "French horn",
    187: "Trumpet",
    188: "Trombone",
    189: "Bowed string instrument",
    190: "String section",
    191: "Violin, fiddle",
    192: "Pizzicato",
    193: "Cello",
    194: "Double bass",
    195: "Wind instrument, woodwind instrument",
    196: "Flute",
    197: "Saxophone",
    198: "Clarinet",
    199: "Harp",
    200: "Bell",
    201: "Church bell",
    202: "Jingle bell",
    203: "Bicycle bell",
    204: "Tuning fork",
    205: "Chime",
    206: "Wind chime",
    207: "Change ringing (campanology)",
    208: "Harmonica",
    209: "Accordion",
    210: "Bagpipes",
    211: "Didgeridoo",
    212: "Shofar",
    213: "Theremin",
    214: "Singing bowl",
    215: "Scratching (performance technique)",
    216: "Pop music",
    217: "Hip hop music",
    218: "Beatboxing",
    219: "Rock music",
    220: "Heavy metal",
    221: "Punk rock",
    222: "Grunge",
    223: "Progressive rock",
    224: "Rock and roll",
    225: "Psychedelic rock",
    226: "Rhythm and blues",
    227: "Soul music",
    228: "Reggae",
    229: "Country",
    230: "Swing music",
    231: "Bluegrass",
    232: "Funk",
    233: "Folk music",
    234: "Middle Eastern music",
    235: "Jazz",
    236: "Disco",
    237: "Classical music",
    238: "Opera",
    239: "Electronic music",
    240: "House music",
    241: "Techno",
    242: "Dubstep",
    243: "Drum and bass",
    244: "Electronica",
    245: "Electronic dance music",
    246: "Ambient music",
    247: "Trance music",
    248: "Music of Latin America",
    249: "Salsa music",
    250: "Flamenco",
    251: "Blues",
    252: "Music for children",
    253: "New-age music",
    254: "Vocal music",
    255: "A capella",
    256: "Music of Africa",
    257: "Afrobeat",
    258: "Christian music",
    259: "Gospel music",
    260: "Music of Asia",
    261: "Carnatic music",
    262: "Music of Bollywood",
    263: "Ska",
    264: "Traditional music",
    265: "Independent music",
    266: "Song",
    267: "Background music",
    268: "Theme music",
    269: "Jingle (music)",
    270: "Soundtrack music",
    271: "Lullaby",
    272: "Video game music",
    273: "Christmas music",
    274: "Dance music",
    275: "Wedding music",
    276: "Happy music",
    277: "Funny music",
    278: "Sad music",
    279: "Tender music",
    280: "Exciting music",
    281: "Angry music",
    282: "Scary music",
    283: "Wind",
    284: "Rustling leaves",
    285: "Wind noise (microphone)",
    286: "Thunderstorm",
    287: "Thunder",
    288: "Water",
    289: "Rain",
    290: "Raindrop",
    291: "Rain on surface",
    292: "Stream",
    293: "Waterfall",
    294: "Ocean",
    295: "Waves, surf",
    296: "Steam",
    297: "Gurgling",
    298: "Fire",
    299: "Crackle",
    300: "Vehicle",
    301: "Boat, Water vehicle",
    302: "Sailboat, sailing ship",
    303: "Rowboat, canoe, kayak",
    304: "Motorboat, speedboat",
    305: "Ship",
    306: "Motor vehicle (road)",
    307: "Car",
    308: "Vehicle horn, car horn, honking",
    309: "Toot",
    310: "Car alarm",
    311: "Power windows, electric windows",
    312: "Skidding",
    313: "Tire squeal",
    314: "Car passing by",
    315: "Race car, auto racing",
    316: "Truck",
    317: "Air brake",
    318: "Air horn, truck horn",
    319: "Reversing beeps",
    320: "Ice cream truck, ice cream van",
    321: "Bus",
    322: "Emergency vehicle",
    323: "Police car (siren)",
    324: "Ambulance (siren)",
    325: "Fire engine, fire truck (siren)",
    326: "Motorcycle",
    327: "Traffic noise, roadway noise",
    328: "Rail transport",
    329: "Train",
    330: "Train whistle",
    331: "Train horn",
    332: "Railroad car, train wagon",
    333: "Train wheels squealing",
    334: "Subway, metro, underground",
    335: "Aircraft",
    336: "Aircraft engine",
    337: "Jet engine",
    338: "Propeller, airscrew",
    339: "Helicopter",
    340: "Fixed-wing aircraft, airplane",
    341: "Bicycle",
    342: "Skateboard",
    343: "Engine",
    344: "Light engine (high frequency)",
    345: "Dental drill, dentist's drill",
    346: "Lawn mower",
    347: "Chainsaw",
    348: "Medium engine (mid frequency)",
    349: "Heavy engine (low frequency)",
    350: "Engine knocking",
    351: "Engine starting",
    352: "Idling",
    353: "Accelerating, revving, vroom",
    354: "Door",
    355: "Doorbell",
    356: "Ding-dong",
    357: "Sliding door",
    358: "Slam",
    359: "Knock",
    360: "Tap",
    361: "Squeak",
    362: "Cupboard open or close",
    363: "Drawer open or close",
    364: "Dishes, pots, and pans",
    365: "Cutlery, silverware",
    366: "Chopping (food)",
    367: "Frying (food)",
    368: "Microwave oven",
    369: "Blender",
    370: "Water tap, faucet",
    371: "Sink (filling or washing)",
    372: "Bathtub (filling or washing)",
    373: "Hair dryer",
    374: "Toilet flush",
    375: "Toothbrush",
    376: "Electric toothbrush",
    377: "Vacuum cleaner",
    378: "Zipper (clothing)",
    379: "Keys jangling",
    380: "Coin (dropping)",
    381: "Scissors",
    382: "Electric shaver, electric razor",
    383: "Shuffling cards",
    384: "Typing",
    385: "Typewriter",
    386: "Computer keyboard",
    387: "Writing",
    388: "Alarm",
    389: "Telephone",
    390: "Telephone bell ringing",
    391: "Ringtone",
    392: "Telephone dialing, DTMF",
    393: "Dial tone",
    394: "Busy signal",
    395: "Alarm clock",
    396: "Siren",
    397: "Civil defense siren",
    398: "Buzzer",
    399: "Smoke detector, smoke alarm",
    400: "Fire alarm",
    401: "Foghorn",
    402: "Whistle",
    403: "Steam whistle",
    404: "Mechanisms",
    405: "Ratchet, pawl",
    406: "Clock",
    407: "Tick",
    408: "Tick-tock",
    409: "Gears",
    410: "Pulleys",
    411: "Sewing machine",
    412: "Mechanical fan",
    413: "Air conditioning",
    414: "Cash register",
    415: "Printer",
    416: "Camera",
    417: "Single-lens reflex camera",
    418: "Tools",
    419: "Hammer",
    420: "Jackhammer",
    421: "Sawing",
    422: "Filing (rasp)",
    423: "Sanding",
    424: "Power tool",
    425: "Drill",
    426: "Explosion",
    427: "Gunshot, gunfire",
    428: "Machine gun",
    429: "Fusillade",
    430: "Artillery fire",
    431: "Cap gun",
    432: "Fireworks",
    433: "Firecracker",
    434: "Burst, pop",
    435: "Eruption",
    436: "Boom",
    437: "Wood",
    438: "Chop",
    439: "Splinter",
    440: "Crack",
    441: "Glass",
    442: "Chink, clink",
    443: "Shatter",
    444: "Liquid",
    445: "Splash, splatter",
    446: "Slosh",
    447: "Squish",
    448: "Drip",
    449: "Pour",
    450: "Trickle, dribble",
    451: "Gush",
    452: "Fill (with liquid)",
    453: "Spray",
    454: "Pump (liquid)",
    455: "Stir",
    456: "Boiling",
    457: "Sonar",
    458: "Arrow",
    459: "Whoosh, swoosh, swish",
    460: "Thump, thud",
    461: "Thunk",
    462: "Electronic tuner",
    463: "Effects unit",
    464: "Chorus effect",
    465: "Basketball bounce",
    466: "Bang",
    467: "Slap, smack",
    468: "Whack, thwack",
    469: "Smash, crash",
    470: "Breaking",
    471: "Bouncing",
    472: "Whip",
    473: "Flap",
    474: "Scratch",
    475: "Scrape",
    476: "Rub",
    477: "Roll",
    478: "Crushing",
    479: "Crumpling, crinkling",
    480: "Tearing",
    481: "Beep, bleep",
    482: "Ping",
    483: "Ding",
    484: "Clang",
    485: "Squeal",
    486: "Creak",
    487: "Rustle",
    488: "Whir",
    489: "Clatter",
    490: "Sizzle",
    491: "Clicking",
    492: "Clickety-clack",
    493: "Rumble",
    494: "Plop",
    495: "Jingle, tinkle",
    496: "Hum",
    497: "Zing",
    498: "Boing",
    499: "Crunch",
    500: "Silence",
    501: "Sine wave",
    502: "Harmonic",
    503: "Chirp tone",
    504: "Sound effect",
    505: "Pulse",
    506: "Inside, small room",
    507: "Inside, large room or hall",
    508: "Inside, public space",
    509: "Outside, urban or manmade",
    510: "Outside, rural or natural",
    511: "Reverberation",
    512: "Echo",
    513: "Noise",
    514: "Environmental noise",
    515: "Static",
    516: "Mains hum",
    517: "Distortion",
    518: "Sidetone",
    519: "Cacophony",
    520: "White noise",
    521: "Pink noise",
    522: "Throbbing",
    523: "Vibration",
    524: "Television",
    525: "Radio",
    526: "Field recording",
}


@AnalyserPluginManager.export("audio_classification")
class AudioClassification(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.model = None
        # self.label_map = None

        # self.model_name = self.config.get("model", "audio_classification_model")

    def split_audio_fd_with_librosa(
        self,
        audio_fd: BinaryIO,
        segments: List[Tuple[float, float]],
        target_sr: int = None,
        mono: bool = False,
        output_format: str = "WAV",
    ) -> List[str]:
        """Loads an audio file descriptor using librosa, cuts specified segments, and writes them to temporary files.

        :param audio_fd: Open readable binary file descriptor/object (e.g. open('...', 'rb')).
        :param segments: List of (start_sec, end_sec) tuples in seconds.
        :param target_sr: Target sample rate. If None, preserves the original native sample rate.
        :param mono: If True, downmixes to mono. If False, retains original channel count.
        :param output_format: Format string recognized by soundfile (e.g., 'WAV', 'FLAC', 'OGG').
        :return: List of file paths pointing to the generated temp files.
        """

        import csv
        import tempfile
        import librosa
        import soundfile as sf

        # Reset file pointer to the beginning if seekable
        if hasattr(audio_fd, "seek"):
            audio_fd.seek(0)

        # sr=None preserves original sampling rate (default librosa resamples to 22050 Hz)
        # mono=False preserves stereo/multichannel tracks
        y, sr = librosa.load(audio_fd, sr=target_sr, mono=mono)

        temp_filepaths: List[str] = []

        for start_sec, end_sec in segments:
            start_sample = int(start_sec * sr)
            end_sample = int(end_sec * sr)

            # Slice the numpy array:
            # If mono: 1D array of shape (samples,)
            # If multi-channel: 2D array of shape (channels, samples)
            if y.ndim > 1:
                chunk = y[:, start_sample:end_sample]
                # soundfile.write expects (samples, channels)
                chunk = chunk.T
            else:
                chunk = y[start_sample:end_sample]

            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{output_format.lower()}"
            )
            try:
                sf.write(temp_file.name, chunk, sr, format=output_format)
                temp_filepaths.append(temp_file.name)
            finally:
                temp_file.close()

        return temp_filepaths

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import torchaudio
        import torch
        import soundfile as sf
        import numpy as np
        from transformers import AutoModel
        import csv
        import tempfile
        from typing import BinaryIO, List, Tuple
        import librosa

        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        def aggregate_probs(
            top3_label_probs: List[Tuple[List[str], List[float]]],
        ) -> List[Tuple[str, float]]:
            """
            Aggregates probabilities of each label across segments
            """
            label_probs = {}
            for labels, probs in top3_label_probs:
                for l, p in zip(labels, probs):
                    if l in label_probs:
                        label_probs[l] += p
                    else:
                        label_probs[l] = p

            total_prob = sum(label_probs.values())
            for l in label_probs:
                label_probs[l] /= total_prob

            top3_label_probs = sorted(
                label_probs.items(), key=lambda x: x[1], reverse=True
            )[:3]
            return top3_label_probs

        def classify_segments(audio_file: str) -> List[Tuple[str, float]]:
            results = []
            target_length = 1024
            norm_mean = -4.268
            norm_std = 4.569
            # Load and resample audio
            wav, sr = sf.read(audio_file)
            waveform = torch.tensor(wav).float()

            if self.device == "cuda":
                waveform = waveform.cuda()
            if sr != 16000:
                waveform = torchaudio.functional.resample(waveform, sr, 16000)

            # Normalize and convert to mel-spectrogram
            waveform = waveform - waveform.mean()
            mel = torchaudio.compliance.kaldi.fbank(
                waveform.unsqueeze(0),
                htk_compat=True,
                sample_frequency=16000,
                use_energy=False,
                window_type="hanning",
                num_mel_bins=128,
                dither=0.0,
                frame_shift=10,
            ).unsqueeze(0)

            # Pad or truncate
            n_frames = mel.shape[1]
            if n_frames < target_length:
                mel = torch.nn.ZeroPad2d((0, 0, 0, target_length - n_frames))(mel)
            else:
                mel = mel[:, :target_length, :]

            # Normalize
            mel = (mel - norm_mean) / (norm_std * 2)
            mel = mel.unsqueeze(0)
            if self.device == "cuda":
                mel = mel.cuda()  # shape: [1, 1, T, F]

            with torch.no_grad():
                logits = self.model(mel)
                probs = torch.sigmoid(logits)
                values, indices = torch.topk(probs, parameters.get("top_k", 3), dim=1)
                print(values, indices)

                print("\n************ Acoustic Event Inference ************")
                print("LABEL".ljust(30) + "PREDICTION")
                for i, v in zip(indices[0], values[0]):
                    print(f"{AUDIO_CLASSIFICATION_VOCAB[i.item()]:<30} {v.item():.3f}")
                    if v.item() > parameters.get("threshold", 0.5):
                        results.append(
                            (
                                AUDIO_CLASSIFICATION_VOCAB[i.item()],
                                v.item(),
                            )
                        )
                print("**************************************************\n")
            return results

        if self.model is None:
            model_id = "worstchan/EAT-base_epoch30_finetune_AS2M"
            self.model = AutoModel.from_pretrained(
                model_id, trust_remote_code=True
            ).eval()

            if self.device == "cuda":
                self.model = self.model.cuda()

        with (
            inputs["audio"] as input_audio,
            inputs["shots"] as input_shots,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            segments = [(shot.start, shot.end) for shot in input_shots.shots]
            with input_audio.open_audio("r") as audio_file:
                audio_splits = self.split_audio_fd_with_librosa(
                    segments=segments, audio_fd=audio_file
                )

                for i, audio_split in enumerate(audio_splits):
                    results = classify_segments(audio_split)
                    output_data.annotations.append(
                        Annotation(
                            start=segments[i][0],
                            end=segments[i][1],
                            labels=[x[0] for x in results],
                        )
                    )
                    # for x in results:
                    #     output_data.annotations.append(
                    #         Annotation(
                    #             start=segments[i][0],
                    #             end=segments[i][1],
                    #             labels=x[0],
                    #         )
                    #     )
                self.update_callbacks(callbacks, progress=1.0)
                # TODO maybe separate shot and speaker annotations in two entries
                return {
                    "annotations": output_data,
                }
