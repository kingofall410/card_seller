from django.db import models
from django.core.files import File
import os

class CropParams(models.Model):
        
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    rotate = models.FloatField(default=0.0)
    display_offset_left = models.FloatField(default=0.0)
    display_offset_top = models.FloatField(default=0.0)
    img = models.ForeignKey('core.CroppedImage', on_delete=models.DO_NOTHING, related_name="crop_params", null=True)

    @classmethod
    def create(cls, image, x=0, y=0, width=0, height=0, left=0, top=0, rotate=0.0):
        instance = cls()

        instance.img = image
        instance.x = x
        instance.y = y

        instance.width = width
        instance.height = height
        instance.rotate = rotate
        instance.display_offset_left = left
        instance.display_offset_top = top
        instance.save()
        return instance
    
    @classmethod
    def clone(cls, crop_params):
        instance = CropParams.create(None, crop_params.x, crop_params.y, crop_params.width, crop_params.height, crop_params.display_offset_left, crop_params.display_offset_top, crop_params.rotate)
        return instance

class CroppedImage(models.Model):
    
    create_date = models.DateTimeField(auto_now_add=True)

    #upload_filepath = models.CharField(max_length=250, blank=True)
    img = models.ImageField(blank=True)

    def url(self):
        return self.img.url 
           
    def path(self):
        return self.img.path      
    
    def update(self,content, crop_params):
        
        #save new crop params
        #delete the old and link the new
        self.crop_params.x = crop_params.x
        self.crop_params.y = crop_params.y
        self.crop_params.width = crop_params.width
        self.crop_params.height = crop_params.height
        self.crop_params.display_offset_left = crop_params.display_offset_left
        self.crop_params.display_offset_top = crop_params.display_offset_top
        crop_params.img=self
        crop_params.save()

        #save the image file
        self.img.save(name=self.img.name, content=content, save=True)

        self.save()
        
    @classmethod
    def create(cls, save_to_filepath=None, content=None, crop_params=None):
        instance = cls()
        instance.save()
        if crop_params:
            crop_params.img=instance
            crop_params.save()
            instance.save()
            print("updated cp")
        else:
            cp = CropParams.create(image=instance)
            print("new cp:", cp.id)
        
        if save_to_filepath:
            name = os.path.basename(save_to_filepath)

            if content is None:
                with open(save_to_filepath, "rb") as f:
                    instance.img.save(name=name, content=File(f), save=False)
            else:
                instance.img.save(name=name, content=content, save=False)

        instance.save()
        return instance
