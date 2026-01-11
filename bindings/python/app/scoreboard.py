#!/usr/bin/env python
# Display a runtext with double-buffering.
from samplebase import SampleBase
from argparse import ArgumentTypeError
from rgbmatrix import graphics
import time

def color(value):
    try:
        return graphics.Color(*[int(v) for v in value.split(",")])
    except:
        raise ArgumentTypeError(f"{value} is an invalid color value. Expected R,G,B values between 0-255, ex: 255,255,255")

class RunText(SampleBase):
    def __init__(self, *args, **kwargs):
        super(RunText, self).__init__(*args, **kwargs)
        self.parser.add_argument("-t", "--text", help="The text to scroll on the RGB LED panel", default="Hello world!")

        self.parser.add_argument("-y", type=int, help="Shift Y-Origin of displaying text (Default: 10)", default=10)
        self.parser.add_argument("-k", "--blink", help="Blink while scrolling. Keep on and off for these amount of scrolled pixels. Ex: 10,5", default=None)

        self.parser.add_argument("-C", "--text-color", type=color, help="Text color. Default 255,255,255 (white)", default="255,255,255")
        self.parser.add_argument("-B", "--background-color", type=color, help="Background color. Default 0,0,0 (white)", default="0,0,0")

    def updateClock(self, canvas, time, font):
        x_time = 15
        y_time = 10
 
        #time background color
        for y in range(0,12):
            for x in range(0,64):
                canvas.SetPixel(x, y, 10,10,10)
        len = graphics.DrawText(canvas, font, x_time, y_time, self.args.text_color, time)

    def run(self):
        bg_color = self.args.background_color

        main_canvas = self.matrix.CreateFrameCanvas()
        bg_canvas = self.matrix.CreateFrameCanvas()
        bg_canvas.Fill(bg_color.red, bg_color.green, bg_color.blue)

        score_font = graphics.Font()
        score_font.LoadFont("../../../fonts/10x20.bdf")
        clock_font = graphics.Font()
        clock_font.LoadFont("../../../fonts/7x13B.bdf")

        x_pos = main_canvas.width
        
        score_y = 29
        score_x_padding = 5
        score_text_color = graphics.Color(255,255,255)
        
        x_pos_1 = 1 + score_x_padding
        y_pos_1 = score_y
        score_1 = "25"

        x_pos_2 = 43 - score_x_padding
        y_pos_2 = score_y
        score_2 = "14"

        text_time = "03:12"

        main_canvas.Fill(bg_color.red, bg_color.green, bg_color.blue)
        i = 59
        while(i > 0):
            i -= 1

            #team 1 background color
            for y in range(13,32):
                for x in range(0,32):
                    main_canvas.SetPixel(x, y, 0,80,30)
            #team 2 background color
            for y in range(13,32):
                for x in range(32, 64):
                    main_canvas.SetPixel(x, y, 80,0,30)
            
            # Draw Scores
            graphics.DrawText(main_canvas, score_font, x_pos_1, y_pos_1, score_text_color, score_1)
            graphics.DrawText(main_canvas, score_font, x_pos_2, y_pos_2, score_text_color, score_2)
            
            # Draw line divider
            line_color = graphics.Color(255,255,255)
            graphics.DrawLine(main_canvas, 0, 12, 63, 12, line_color)
            
            time_str = str(i)
            if len(time_str) == 2:
                self.updateClock(main_canvas, "05:" + str(i), clock_font)
            else:
                self.updateClock(main_canvas, "05:0" + str(i), clock_font)
            main_canvas = self.matrix.SwapOnVSync(main_canvas)
            time.sleep(1)

# Main function
if __name__ == "__main__":
    run_text = RunText()
    if (not run_text.process()):
        run_text.print_help()
